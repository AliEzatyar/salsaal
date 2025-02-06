from django import template

register = template.Library()

@register.simple_tag
def update_query(request,**kwargs):
    pre_params = request.GET.copy()
    for key,value in kwargs.items():
        pre_params[key] = value
    return "?"+ pre_params.urlencode()             