import json
from functools import update_wrapper
from urllib.parse import urlencode

from django import http
from django.conf import settings
from django.conf.urls import url, include
from django.core.serializers.json import DjangoJSONEncoder
from django.core import serializers
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from django.contrib.admin import actions
from django.contrib.admin import site as django_site
from django.contrib.admin import (
        AdminSite as DjangoAdminSite,
        ModelAdmin as DjangoModelAdmin,
        autodiscover as django_admin_autodiscover)
from .serializers import ModelAdminSerializer


class ModelAdmin(DjangoModelAdmin):
    HTTP_METHOD_NAMES = ['GET', 'POST', 'PUT', 'DELETE']

    def api_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urlpatterns = [
            url(r'^$',
                wrap(self.admin_site.admin_view(self.dispatch)),
                name='%s_%s_api_list' % info),
            url(r'^meta/$',
                wrap(self.admin_site.admin_view(self.api_meta_view)),
                name='%s_%s_api_meta' % info),
            url(r'^(?P<pk>[-\w]+)/$',
                wrap(self.admin_site.admin_view(self.dispatch)),
                name='%s_%s_api_detail' % info),
        ]
        return urlpatterns

    def http_method_not_allowed(self, request, *args, **kwargs):
        if settings.DEBUG and self.HTTP_METHOD_NAMES:
            raise Exception(
                "Only: {}".format(", ".join(self.HTTP_METHOD_NAMES))
            )
        return http.HttpResponseNotAllowed(self.HTTP_METHOD_NAMES)

    def api_meta_view(self, request, *args, **kwargs):
        return HttpResponse(
            json.dumps(ModelAdminSerializer(
                model_admin=self,
                admin_form=self.get_form(request),
            ).data),
            content_type='application/json',
        )

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        handlers = {
            "GET": self.api_get,
            "POST": self.api_create,
            "PUT": self.api_update,
            "DELETE": self.api_delete,
        }
        handler = handlers.get(
            request.method,
            self.http_method_not_allowed)
        return handler(request, *args, **kwargs)

    def __update_instance(self, request, instance=None):
        data = json.loads(request.body)
        ModelForm = self.get_form(request, obj=instance)
        form = ModelForm(data=data, files=request.FILES)
        if not form.is_valid():
            errors = {"errors": json.loads(form.errors.as_json())}
            return HttpResponse(json.dumps(errors),
                                status=400,
                                content_type="application/json")
        obj = form.save()
        data = self.obj_as_dict(request, obj)
        return HttpResponse(
            json.dumps(
                {
                    self.model._meta.verbose_name: self.obj_as_dict(
                        request, form.instance, self.fields)
                },
                cls=DjangoJSONEncoder),
            content_type='application/json',
        )

    def api_create(self, request, *args, **kwargs):
        if kwargs.get("pk"):
            return self.http_method_not_allowed(request, *args, **kwargs)
        return self.__update_instance(request)

    def api_update(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        if not pk:
            return self.http_method_not_allowed(request, *args, **kwargs)
        return self.__update_instance(request, self.model.objects.get(pk))

    def api_delete(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        if not pk:
            return self.http_method_not_allowed(request, *args, **kwargs)
        self.model.objects.get(pk).delete()
        return HttpResponse({"deleted": True})

    def api_get(self, request, *args, **kwargs):
        if kwargs.get("pk"):
            return self.api_detail(request, *args, **kwargs)
        else:
            return self.api_list(request, *args, **kwargs)

    def get_model_admin_field_names(self, request, obj):
        """
            This method return admin class readonly custom fields.
            Getting ModelAdmin list_display + readonly_fields
        """
        return set(
            self.get_readonly_fields(request, obj)
        ) | set(
            self.get_list_display(request)
        )

    def serialize_objs(self, objs):
        data_objs = json.loads(serializers.serialize('json', objs))
        for data in data_objs:
            data.update(data["fields"])
            del data["fields"]
        return data_objs

    def serialize_obj(self, obj):
        return self.serialize_objs([obj])[0]

    def obj_as_dict(self, request, obj, fields):
        data = self.serialize_obj(obj)
        # serialize model instance fields datas
        for field in obj._meta.get_fields():
            if not (field.is_relation and field.concrete):
                continue
            field_value = getattr(obj, field.name)
            if not field_value:
                continue
            if field.many_to_many:
                data[field.name] = self.serialize_objs(field_value.all())
            elif field.many_to_one or field.one_to_one or field.one_to_many:
                data[field.name] = self.serialize_obj(field_value)

        # add custom admin class field to serialized bundle
        model_admin_fields = self.get_model_admin_field_names(request, obj)
        for field in model_admin_fields:
            if field in data:
                continue

            if hasattr(obj, field):
                f = getattr(obj, field)
                data[field] = str(f)

            if hasattr(self, field):
                field_method = getattr(self, field)
                if callable(field_method):
                    data[field] = field_method()
                else:
                    data[field] = field_method

        info = self.model._meta.app_label, self.model._meta.model_name
        data = {k: v for k, v in data.items()
                if k in set(fields or self.get_fields(request))}
        data["admin_detail_url"] = str(
            reverse("admin:{}_{}_change".format(*info), args=(obj.pk,))
        )
        return data

    def get_api_page_url(self, request, cl, page_diff):
        page_num = cl.page_num
        if page_num and page_num is not int or not cl.multi_page:
            return None
        info = self.model._meta.app_label, self.model._meta.model_name
        url = reverse("admin:%s_%s_api_list" % info)
        host = request.get_host()
        params = cl.params
        params["p"] = page_num + 1
        return "%s://%s%s?%s" % (request.scheme, host, url, urlencode(params))

    def api_list(self, request, *args, **kwargs):
        cl = self.get_changelist_instance(request)
        cl.get_results(request)
        data = {
            "count": cl.result_count,
            "next": self.get_api_page_url(request, cl, 1),
            "previous": self.get_api_page_url(request, cl, -1),
            str(self.model._meta.verbose_name_plural): [
                self.obj_as_dict(request, item, self.list_display)
                for item in cl.result_list
            ],
        }
        return HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder),
            content_type='application/json')

    def api_detail(self, request, *args, **kwargs):
        obj = self.get_object(request, object_id=kwargs.get("pk"))
        ModelForm = self.get_form(request, obj=obj)
        form = ModelForm(instance=obj)
        return HttpResponse(
            json.dumps(
                {
                    self.model._meta.verbose_name: self.obj_as_dict(
                        request, form.instance, self.fields)
                },
                cls=DjangoJSONEncoder),
            content_type='application/json',
        )


class AdminoSite(DjangoAdminSite):

    def __init__(self, django_site, name='admino'):
        self.django_site = django_site
        self._registry = {}
        self.name = name
        self._actions = {'delete_selected': actions.delete_selected}
        self._global_actions = self._actions.copy()

    def activated(self):
        django_admin_registered_apps = self.django_site._registry
        for model, admin_obj in django_admin_registered_apps.items():
            self._registry[model] = type(
                "ModelAdmino",
                (ModelAdmin, DjangoModelAdmin),
                {"admin_type": "admino"}
            )(
                model,
                self
            )
        django_admin_autodiscover()
        return self

    def get_urls(self):
        urlpatterns = super(AdminoSite, self).get_urls()
        valid_app_labels = []
        for model, model_admin in self._registry.items():
            api_urlpatterns = [
                url(
                    r'api/{}/{}/'.format(
                        model._meta.app_label,
                        model._meta.verbose_name_plural,
                    ),
                    include(model_admin.api_urls())
                ),
            ]
            urlpatterns = urlpatterns + api_urlpatterns
            if model._meta.app_label not in valid_app_labels:
                valid_app_labels.append(model._meta.app_label)
        return urlpatterns


site = AdminoSite(django_site=django_site)
