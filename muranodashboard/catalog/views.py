#    Copyright (c) 2014 Mirantis, Inc.
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

import collections
import copy
import functools
import json
import logging
import re

from django.conf import settings
from django.contrib import auth
from django.contrib.auth import decorators as auth_dec
from django.contrib.formtools.wizard import views as wizard_views
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse
from django import http
from django import shortcuts
from django.utils import decorators as django_dec
from django.utils import http as http_utils
from django.utils.translation import ugettext_lazy as _
from django.views.generic import list as list_view
from horizon import exceptions
from horizon.forms import views
from horizon import messages
from horizon import tabs

from muranoclient.common import exceptions as exc
from muranodashboard import api
from muranodashboard.api import packages as pkg_api
from muranodashboard.catalog import tabs as catalog_tabs
from muranodashboard.dynamic_ui import helpers
from muranodashboard.dynamic_ui import services
from muranodashboard.environments import api as env_api
from muranodashboard.environments import consts
from muranodashboard import utils


LOG = logging.getLogger(__name__)
ALL_CATEGORY_NAME = 'All'
LATEST_APPS_QUEUE_LIMIT = 6


class DictToObj(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)


def get_available_environments(request):
    envs = []
    for env in env_api.environments_list(request):
        obj = DictToObj(id=env.id, name=env.name, status=env.status)
        envs.append(obj)

    return envs


def is_valid_environment(environment, valid_environments):
    for env in valid_environments:
        if environment.id == env.id:
            return True
    return False


def get_environments_context(request):
    envs = get_available_environments(request)
    context = {'available_environments': envs}
    environment = request.session.get('environment')
    if environment and is_valid_environment(environment, envs):
        context['environment'] = environment
    elif envs:
        context['environment'] = envs[0]
    return context


@auth_dec.login_required
def switch(request, environment_id,
           redirect_field_name=auth.REDIRECT_FIELD_NAME):
    redirect_to = request.REQUEST.get(redirect_field_name, '')
    if not http_utils.is_safe_url(url=redirect_to, host=request.get_host()):
        redirect_to = settings.LOGIN_REDIRECT_URL

    for env in get_available_environments(request):
        if env.id == environment_id:
            request.session['environment'] = env
            break
    return shortcuts.redirect(redirect_to)


def create_quick_environment(request):
    quick_env_prefix = 'quick-env-'
    quick_env_re = re.compile('^' + quick_env_prefix + '([\d]+)$')

    def parse_number(env):
        match = re.match(quick_env_re, env.name)
        return int(match.group(1)) if match else 0

    numbers = [parse_number(e) for e in env_api.environments_list(request)]
    new_env_number = 1
    if numbers:
        numbers.sort()
        new_env_number = numbers[-1] + 1

    params = {'name': quick_env_prefix + str(new_env_number)}
    return env_api.environment_create(request, params)


def update_latest_apps(func):
    """Adds package id to a session queue with Applications which were
    recently added to an environment or to the Catalog itself. Thus it is
    used as decorator for views adding application to an environment or
    uploading new package definition to a catalog.
    """
    @functools.wraps(func)
    def __inner(request, **kwargs):
        apps = request.session.setdefault('latest_apps', collections.deque())
        app_id = kwargs['app_id']
        if app_id in apps:  # move recent app to the beginning
            apps.remove(app_id)

        apps.appendleft(app_id)
        if len(apps) > LATEST_APPS_QUEUE_LIMIT:
            apps.pop()

        return func(request, **kwargs)

    return __inner


def clean_latest_apps(request):
    cleaned_apps, cleaned_app_ids = [], []
    for app_id in request.session.get('latest_apps', []):
        try:
            app = api.muranoclient(request).packages.get(app_id)
        except exc.HTTPNotFound:
            pass
        else:
            cleaned_apps.append(app)
            cleaned_app_ids.append(app_id)
    request.session['latest_apps'] = collections.deque(cleaned_app_ids)
    return cleaned_apps


def clear_forms_data(func):
    """Clears user's session from a data for a specific application. It
    guarantees that previous additions of that application won't interfere
    with the next ones. Should be used as a decorator for entry points for
    adding an application in an environment.
    """
    @functools.wraps(func)
    def __inner(request, **kwargs):
        app_id = kwargs['app_id']
        fqn = pkg_api.get_app_fqn(request, app_id)
        LOG.debug('Clearing forms data for application {0}.'.format(fqn))
        services.get_apps_data(request)[app_id] = {}
        return func(request, **kwargs)

    return __inner


@update_latest_apps
@clear_forms_data
@auth_dec.login_required
def deploy(request, environment_id, app_id,
           do_redirect=False, drop_wm_form=False):
    view = Wizard.as_view(services.get_app_forms,
                          condition_dict=services.condition_getter)
    return view(request, app_id=app_id, environment_id=environment_id,
                do_redirect=do_redirect, drop_wm_form=drop_wm_form)


@update_latest_apps
@clear_forms_data
@auth_dec.login_required
def quick_deploy(request, app_id):
    env = create_quick_environment(request)
    try:
        return deploy(request, environment_id=env.id, app_id=app_id,
                      do_redirect=True, drop_wm_form=True)
    except Exception:
        env_api.environment_delete(request, env.id)
        raise


def get_image(request, app_id):
    content = pkg_api.get_app_logo(request, app_id)
    if content:
        return http.HttpResponse(content=content, content_type='image/png')
    else:
        universal_logo = static('muranodashboard/images/icon.png')
        return http.HttpResponseRedirect(universal_logo)


class LazyWizard(wizard_views.SessionWizardView):
    """The class which defers evaluation of form_list and condition_dict
    until view method is called. So, each time we load a page with a dynamic
    UI form, it will have markup/logic from the newest YAML-file definition.
    """
    @django_dec.classonlymethod
    def as_view(cls, initforms, *initargs, **initkwargs):
        """Main entry point for a request-response process."""
        # sanitize keyword arguments
        for key in initkwargs:
            if key in cls.http_method_names:
                raise TypeError(u"You tried to pass in the %s method name as a"
                                u" keyword argument to %s(). Don't do that."
                                % (key, cls.__name__))
            if not hasattr(cls, key):
                raise TypeError(u"%s() received an invalid keyword %r" % (
                    cls.__name__, key))

        @update_latest_apps
        def view(request, *args, **kwargs):
            forms = initforms
            if hasattr(initforms, '__call__'):
                forms = initforms(request, kwargs)
            _kwargs = copy.copy(initkwargs)

            _kwargs = cls.get_initkwargs(forms, *initargs, **_kwargs)

            cdict = _kwargs.get('condition_dict')
            if cdict and hasattr(cdict, '__call__'):
                _kwargs['condition_dict'] = cdict(request, kwargs)

            self = cls(**_kwargs)
            if hasattr(self, 'get') and not hasattr(self, 'head'):
                self.head = self.get
            self.request = request
            self.args = args
            self.kwargs = kwargs
            return self.dispatch(request, *args, **kwargs)

        # take name and docstring from class
        functools.update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        functools.update_wrapper(view, cls.dispatch, assigned=())
        return view


class Wizard(views.ModalFormMixin, LazyWizard):
    template_name = 'services/wizard_create.html'
    do_redirect = False

    def get_prefix(self, *args, **kwargs):
        base = super(Wizard, self).get_prefix(*args, **kwargs)
        fmt = utils.BlankFormatter()
        return fmt.format('{0}_{environment_id}_{app_id}', base, **kwargs)

    def done(self, form_list, **kwargs):
        environment_id = kwargs.get('environment_id')
        env_url = reverse('horizon:murano:environments:services',
                          args=(environment_id,))
        app_name = services.get_service_name(self.request,
                                             kwargs.get('app_id'))

        service = form_list[0].service
        attributes = service.extract_attributes()
        attributes = helpers.insert_hidden_ids(attributes)

        storage = attributes.setdefault('?', {}).setdefault(
            consts.DASHBOARD_ATTRS_KEY, {})
        storage['name'] = app_name

        wm_form_data = service.cleaned_data.get('workflowManagement')
        if wm_form_data:
            do_redirect = not wm_form_data['StayAtCatalog']
        else:
            do_redirect = self.get_wizard_flag('do_redirect')

        fail_url = reverse("horizon:murano:environments:index")
        try:
            srv = env_api.service_create(
                self.request, environment_id, attributes)
        except exc.HTTPForbidden:
            msg = _("Sorry, you can't add application right now. "
                    "The environment is deploying.")
            exceptions.handle(self.request, msg, redirect=fail_url)
        except Exception:
            exceptions.handle(self.request,
                              _("Sorry, you can't add application right now."),
                              redirect=fail_url)
        else:
            message = "The '{0}' application successfully " \
                      "added to environment.".format(app_name)

            messages.success(self.request, message)

            if do_redirect:
                return http.HttpResponseRedirect(env_url)
            else:
                srv_id = getattr(srv, '?')['id']
                return self.create_hacked_response(srv_id, attributes['name'])

    def create_hacked_response(self, obj_id, obj_name):
        # copy-paste from horizon.forms.views.ModalFormView; should be done
        # that way until we move here from django Wizard to horizon workflow
        if views.ADD_TO_FIELD_HEADER in self.request.META:
            field_id = self.request.META[views.ADD_TO_FIELD_HEADER]
            response = http.HttpResponse(json.dumps([obj_id, obj_name]))
            response["X-Horizon-Add-To-Field"] = field_id
            return response
        else:
            ns_url = 'horizon:murano:catalog:index'
            return http.HttpResponseRedirect(reverse(ns_url))

    def get_form_initial(self, step):
        init_dict = {'request': self.request,
                     'environment_id': self.kwargs.get('environment_id')}

        return self.initial_dict.get(step, init_dict)

    def _get_wizard_param(self, key):
        param = self.kwargs.get(key)
        return param if param is not None else self.request.POST.get(key)

    def get_wizard_flag(self, key):
        value = self._get_wizard_param(key)
        if isinstance(value, basestring):
            return value.lower() == 'true'
        else:
            return value

    def get_context_data(self, form, **kwargs):
        context = super(Wizard, self).get_context_data(form=form, **kwargs)
        mc = api.muranoclient(self.request)
        app_id = self.kwargs.get('app_id')
        app = mc.packages.get(app_id)
        environment_id = self.kwargs.get('environment_id')
        env = mc.environments.get(environment_id)

        context['field_descriptions'] = services.get_app_field_descriptions(
            self.request, app_id, self.steps.index)
        context.update({'type': app.fully_qualified_name,
                        'service_name': app.name,
                        'app_id': app_id,
                        'environment_id': environment_id,
                        'environment_name': env.name,
                        'do_redirect': self.get_wizard_flag('do_redirect'),
                        'drop_wm_form': self.get_wizard_flag('drop_wm_form'),
                        'prefix': self.prefix,
                        })
        return context


class IndexView(list_view.ListView):
    paginate_by = 6
    pagination_param = 'marker'

    def __init__(self, **kwargs):
        super(IndexView, self).__init__(**kwargs)
        self._more = None

    @staticmethod
    def get_object_id(datum):
        return datum.id

    def get_marker(self):
        """Returns the identifier for the last object in the current data set
        for APIs that use marker/limit-based paging.
        """
        data = self.object_list
        if data:
            return http_utils.urlquote_plus(self.get_object_id(data[-1]))
        else:
            return ''

    def get_pagination_string(self):
        """Returns the query parameter string to paginate this table."""
        return "=".join([self.pagination_param, self.get_marker()])

    def get_queryset(self):
        query_params = {'type': 'Application'}
        category = self.request.GET.get('category', ALL_CATEGORY_NAME)
        marker = self.request.GET.get('marker')
        search = self.request.GET.get('search')
        if search:
            query_params['search'] = search
        else:
            if category != ALL_CATEGORY_NAME:
                query_params['category'] = category

        packages = []
        with api.handled_exceptions(self.request):
            packages, self._more = pkg_api.package_list(
                self.request, filters=query_params, paginate=True,
                marker=marker, page_size=self.paginate_by)

        return packages

    def get_template_names(self):
        return ['catalog/index.html']

    def has_more_data(self):
        return self._more

    def paginate_queryset(self, queryset, page_size):
        # override this method explicitly to skip unnecessary calculations
        # during call to parent's get_context_data() method
        return None, None, queryset, None

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)

        categories = []
        with api.handled_exceptions(self.request):
            client = api.muranoclient(self.request)
            categories = client.packages.categories()

        if ALL_CATEGORY_NAME not in categories:
            categories.insert(0, ALL_CATEGORY_NAME)
        current_category = self.request.GET.get('category', categories[0])
        context.update({
            'categories': categories,
            'current_category': current_category,
            'latest_list': clean_latest_apps(self.request)
        })

        search = self.request.GET.get('search')
        if search:
            context['search'] = search

        context.update(get_environments_context(self.request))

        return context


class AppDetailsView(tabs.TabView):
    tab_group_class = catalog_tabs.ApplicationTabs
    template_name = 'catalog/app_details.html'

    app = None

    def get_data(self, **kwargs):
        LOG.debug(('AppDetailsView get_data: {0}'.format(kwargs)))
        app_id = kwargs.get('application_id')
        self.app = api.muranoclient(self.request).packages.get(app_id)
        return self.app

    def get_context_data(self, **kwargs):
        context = super(AppDetailsView, self).get_context_data(**kwargs)
        LOG.debug('AppDetailsView get_context called with kwargs: {0}'.
                  format(kwargs))
        context['app'] = self.app

        context.update(get_environments_context(self.request))

        return context

    def get_tabs(self, request, *args, **kwargs):
        app = self.get_data(**kwargs)
        return self.tab_group_class(request, application=app, **kwargs)
