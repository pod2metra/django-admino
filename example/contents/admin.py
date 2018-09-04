from django.contrib import admin
from .models import Author, BookType, Book


class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "creation_date")


class BookTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "creation_date")


class BookAdmin(admin.ModelAdmin):
    admin_type = "admino"
    list_display = ("name", "author", "title")
    list_display_links = ("name", "author")
    list_filter = ("author", "name")

    def title(self, obj):
        return "mr %s" % obj.name


admin.site.register(Author, AuthorAdmin)
admin.site.register(BookType, BookTypeAdmin)
admin.site.register(Book, BookAdmin)
