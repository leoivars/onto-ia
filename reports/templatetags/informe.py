from django import template

from reports.markdown import render

register = template.Library()


@register.filter(name="md")
def md(texto):
    return render(texto)
