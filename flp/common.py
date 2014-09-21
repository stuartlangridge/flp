from flp.models import Log

def publicLog(message):
    Log(message=message).save()

def andlist(items):
    if len(items) == 0:
        return ""
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return "%s and %s" % (items[0], items[1])
    else:
        lst = sorted(items)
        lst[-1] = "and %s" % lst[-1]
        return ", ".join(lst)


