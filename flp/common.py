from flp.models import Log

def publicLog(message):
    Log(message=message).save()


