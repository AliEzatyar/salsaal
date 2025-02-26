from django import template

register = template.Library()

@register.simple_tag
def update_query(request,**kwargs):
    pre_params = request.GET.copy()
    for key,value in kwargs.items():
        pre_params[key] = value
    return "?"+ pre_params.urlencode()             

@register.simple_tag
def create_array(num):
    num = int(num)
    return [i for i in range(num)]

@register.filter
def subtract(num1,num2):
    print(num2)
    return int(num1 - num2)