from django.db import models
from django.utils.encoding import smart_text


class BookType(models.Model):
    name = models.CharField(max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return smart_text(self.name)


class Author(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(blank=True, null=True, upload_to="author/")
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str(self):
        return smart_text(self.name)


class Book(models.Model):
    name = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    book_type = models.ManyToManyField(BookType)

    def __str__(self):
        return smart_text(self.name)
