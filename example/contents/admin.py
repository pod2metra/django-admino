from admino.sites import ModelAdmino
from django.contrib import admin
from .models import Author, BookType, Book


class AuthorAdmin(ModelAdmino):
    list_display = ("name", "creation_date")


class BookTypeAdmin(ModelAdmino):
    list_display = ("name", "creation_date")


class BookAdmin(ModelAdmino):
    admin_type = "admino"
    list_display = ("name", "author", "title")
    list_display_links = ("name", "author")
    list_filter = ("author", "name")

    def title(self, obj):
        return "mr %s" % obj.name


class TestAdminoClass(ModelAdmino):
    def api_get(self, request, *args, **kwargs):
        return super(TestAdminoClass, self).api_get(request, *args, **kwargs)


admin.site.register(Author, AuthorAdmin)
admin.site.register(BookType, BookTypeAdmin)
admin.site.register(Book, BookAdmin)
