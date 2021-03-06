# Copyright 2013 NEC Corporation
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
# Copyright (c) 2013-2015 Wind River Systems, Inc.
#

import logging

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms

from openstack_dashboard import api
from openstack_dashboard.dashboards.project.networks.subnets \
    import workflows as project_workflows
from openstack_dashboard.dashboards.project.networks import workflows \
    as network_workflows


LOG = logging.getLogger(__name__)


class CreateSubnetInfoAction(project_workflows.CreateSubnetInfoAction):
    check_subnet_range = False

    # NOTE(amotoki): As of Newton, workflows.Action does not support
    # an inheritance of django Meta class. It seems subclasses must
    # declare django meta class.
    class Meta(object):
        name = _("Subnet")
        help_text = _('Create a subnet associated with the network. '
                      'Advanced configuration is available by clicking on the '
                      '"Subnet Details" tab.')


class CreateSubnetInfo(project_workflows.CreateSubnetInfo):
    action_class = CreateSubnetInfoAction


class CreateSubnetDetailAction(network_workflows.CreateSubnetDetailAction):
    provider_type = forms.CharField(
        label=_("Provider Type"),
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    provider_network = forms.CharField(
        label=_("Provider Network"),
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    provider_id = forms.IntegerField(
        label=_("Provider ID"),
        required=False,
        min_value=network_workflows.MIN_VLAN_TAG,
        max_value=network_workflows.MAX_VLAN_TAG,
        help_text=_(
            "Provider network segment ID of subnet when VLAN is supplied. "
            "Subnets of the same VLAN must use the same segment ID."))

    class Meta(object):
        name = _("Subnet Detail")
        help_text = _('You can specify additional attributes for the subnet.')

    def __init__(self, request, context, *args, **kwargs):
        super(CreateSubnetDetailAction, self).__init__(
            request, context, *args, **kwargs)

        if api.base.is_TiS_region(request):
            network = \
                api.neutron.network_get(request, context['network_id'], False)
            provider_type = network.get('provider:network_type')
            provider_network = network.get('provider:physical_network')

            self.fields['provider_type'].initial = provider_type
            self.fields['provider_network'].initial = provider_network
            if provider_type == 'flat':
                self.fields['provider_id'].widget.attrs['readonly'] = True
        else:
            del self.fields['provider_type']
            del self.fields['provider_network']
            del self.fields['provider_id']


class UpdateSubnetDetailAction(project_workflows.UpdateSubnetDetailAction):
    provider_type = forms.CharField(
        label=_("Provider Type"),
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    provider_network = forms.CharField(
        label=_("Provider Network"),
        required=False,
        widget=forms.TextInput(attrs={'disabled': 'disabled'}))
    provider_id = forms.CharField(
        label=_("Provider ID"),
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly'}))

    class Meta(object):
        name = _("Subnet Detail")
        help_text = _('You can specify additional attributes for the subnet.')

    def __init__(self, request, context, *args, **kwargs):
        super(UpdateSubnetDetailAction, self).__init__(
            request, context, *args, **kwargs)
        if not api.base.is_TiS_region(request):
            del self.fields['provider_type']
            del self.fields['provider_network']
            del self.fields['provider_id']


class CreateSubnetDetail(network_workflows.CreateSubnetDetail):
    action_class = CreateSubnetDetailAction
    contributes = network_workflows.CreateSubnetDetail.contributes \
        + ("provider_type", "provider_network", "provider_id")


class UpdateSubnetDetail(CreateSubnetDetail):
    action_class = UpdateSubnetDetailAction


class CreateSubnet(project_workflows.CreateSubnet):
    default_steps = (CreateSubnetInfo,
                     network_workflows.CreateSubnetDetail)

    def get_success_url(self):
        return reverse("horizon:admin:networks:detail",
                       args=(self.context.get('network_id'),))

    def get_failure_url(self):
        return reverse("horizon:admin:networks:detail",
                       args=(self.context.get('network_id'),))

    def handle(self, request, data):
        try:
            # We must specify tenant_id of the network which a subnet is
            # created for if admin user does not belong to the tenant.
            network = api.neutron.network_get(request,
                                              self.context['network_id'])
        except Exception as e:
            LOG.info('Failed to retrieve network %(id)s for a subnet: %(exc)s',
                     {'id': data['network_id'], 'exc': e})
            msg = (_('Failed to retrieve network %s for a subnet') %
                   data['network_id'])
            redirect = self.get_failure_url()
            exceptions.handle(request, msg, redirect=redirect)
        subnet = self._create_subnet(request, data,
                                     tenant_id=network.tenant_id)
        return True if subnet else False


class UpdateSubnetInfoAction(project_workflows.UpdateSubnetInfoAction):
    check_subnet_range = False

    # NOTE(amotoki): As of Newton, workflows.Action does not support
    # an inheritance of django Meta class. It seems subclasses must
    # declare django meta class.
    class Meta(object):
        name = _("Subnet")
        help_text = _('Update a subnet associated with the network. '
                      'Advanced configuration are available at '
                      '"Subnet Details" tab.')


class UpdateSubnetInfo(project_workflows.UpdateSubnetInfo):
    action_class = UpdateSubnetInfoAction

    def _setup_subnet_parameters(self, params, data, is_create=True):
        super(CreateSubnet, self)._setup_subnet_parameters(
            params, data, is_create)
        if data.get('provider_id'):
            params['wrs-provider:segmentation_id'] = data['provider_id']
            params['wrs-provider:network_type'] = data['provider_type']
            params['wrs-provider:physical_network'] = data['provider_network']


class UpdateSubnet(project_workflows.UpdateSubnet):
    success_url = "horizon:admin:networks:detail"
    failure_url = "horizon:admin:networks:detail"
    default_steps = (project_workflows.UpdateSubnetInfo,
                     UpdateSubnetDetail)

    default_steps = (UpdateSubnetInfo,
                     project_workflows.UpdateSubnetDetail)
