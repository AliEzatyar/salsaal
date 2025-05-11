from django import template

register = template.Library()

@register.filter
def format_datetime(datetime):
    datetime = str(datetime).split()
    date = datetime[0]
    time = datetime[1]
    hour = time.split('.')[0]
    return  hour+"  " + date