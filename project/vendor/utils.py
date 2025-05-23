import re
from unidecode import unidecode
from django.core.exceptions import PermissionDenied

def to_af_weekday(index):
    return (9+ index)%7 +1 