# Copyright 2012 NEC Corporation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Copyright (c) 2013-2017 Wind River Systems, Inc.
#

"""
Views for managing Neutron Networks.
"""
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import tables
from horizon import tabs
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.utils import filters

from openstack_dashboard.dashboards.project.networks \
    import forms as project_forms
from openstack_dashboard.dashboards.project.networks \
    import tables as project_tables
from openstack_dashboard.dashboards.project.networks \
    import tabs as network_tabs
from openstack_dashboard.dashboards.project.networks \
    import workflows as project_workflows
from openstack_dashboard.dashboards.project.networks \
    import wrs_tabs as project_tabs


class IndexView(tables.DataTableView):
    table_class = project_tables.NetworksTable
    page_title = _("Networks")
    FILTERS_MAPPING = {'shared': {_("yes"): True, _("no"): False},
                       'router:external': {_("yes"): True, _("no"): False},
                       'admin_state_up': {_("up"): True, _("down"): False}}

    def get_data(self):
        try:
            tenant_id = self.request.user.tenant_id
            search_opts = self.get_filters(filters_map=self.FILTERS_MAPPING)
            networks = api.neutron.network_list_for_tenant(
                self.request, tenant_id, include_external=True, **search_opts)
        except Exception:
            networks = []
            msg = _('Network list can not be retrieved.')
            exceptions.handle(self.request, msg)
        return networks


class IndexViewTabbed(tabs.TabbedTableView):
    tab_group_class = project_tabs.NetworkTabs
    template_name = 'project/networks/tabs.html'


class DefaultSubnetWorkflowMixin(object):

    def get_default_dns_servers(self):
        # this returns the default dns servers to be used for new subnets
        dns_default = "\n".join(getattr(settings, 'OPENSTACK_NEUTRON_NETWORK',
                                        {}).get('default_dns_nameservers', ''))
        return dns_default


class CreateView(DefaultSubnetWorkflowMixin, workflows.WorkflowView):
    workflow_class = project_workflows.CreateNetwork

    def get_initial(self):
        results = super(CreateView, self).get_initial()
        results['dns_nameservers'] = self.get_default_dns_servers()
        return results


class UpdateView(forms.ModalFormView):
    context_object_name = 'network'
    form_class = project_forms.UpdateNetwork
    form_id = "update_network_form"
    submit_label = _("Save Changes")
    submit_url = "horizon:project:networks:update"
    success_url = reverse_lazy("horizon:project:networks:index")
    template_name = 'project/networks/update.html'
    page_title = _("Edit Network")

    def get_success_url(self):
        http_referer = self.request.META.get('HTTP_REFERER')
        if http_referer is None or "detail" not in http_referer:
            return self.success_url
        network_id = self.kwargs['network_id']
        detail_url = self.submit_url.replace("update", "detail")
        return reverse(detail_url, args=[network_id])

    def get_context_data(self, **kwargs):
        context = super(UpdateView, self).get_context_data(**kwargs)
        args = (self.kwargs['network_id'],)
        context["network_id"] = self.kwargs['network_id']
        context["submit_url"] = reverse(self.submit_url, args=args)
        return context

    @memoized.memoized_method
    def _get_object(self, *args, **kwargs):
        network_id = self.kwargs['network_id']
        try:
            # no subnet values are read or editable in this view, so
            # save the subnet expansion overhead
            return api.neutron.network_get(self.request, network_id,
                                           expand_subnet=False)
        except Exception:
            redirect = self.success_url
            msg = _('Unable to retrieve network details.')
            exceptions.handle(self.request, msg, redirect=redirect)

    def get_initial(self):
        network = self._get_object()
        data = {'network_id': network['id'],
                'tenant_id': network['tenant_id'],
                'name': network['name'],
                'admin_state': network['admin_state_up'],
                'vlan_transparent': network.get(['vlan_transparent']),
                'qos': network.get('qos'),
                'shared': network['shared']}
        return data


class DetailView(tabs.TabbedTableView):
    tab_group_class = network_tabs.NetworkDetailsTabs
    template_name = 'horizon/common/_detail.html'
    page_title = '{{ network.name | default:network.id }}'

    @staticmethod
    def get_redirect_url():
        return reverse('horizon:project:networks:index')

    @memoized.memoized_method
    def _get_data(self):
        try:
            network_id = self.kwargs['network_id']
            network = api.neutron.network_get(self.request, network_id)
            network.set_id_as_name_if_empty(length=0)
            if network.qos:
                network.qos_policy = api.neutron.qos_get(
                    self.request, network.qos)
        except Exception:
            msg = _('Unable to retrieve details for network "%s".') \
                % (network_id)
            exceptions.handle(self.request, msg,
                              redirect=self.get_redirect_url())
        return network

    def get_subnets_data(self):
        # MultiTableMixin requires this method to be defined
        pass

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        network = self._get_data()
        context["network"] = network
        table = project_tables.NetworksTable(self.request)
        context["url"] = self.get_redirect_url()
        context["actions"] = table.render_row_actions(network)
        choices = project_tables.STATUS_DISPLAY_CHOICES
        network.status_label = (
            filters.get_display_label(choices, network.status))
        choices = project_tables.DISPLAY_CHOICES
        network.admin_state_label = (
            filters.get_display_label(choices, network.admin_state))
        return context
