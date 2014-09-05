from flp.models import Blog, Score
from django.db.models import Sum
import datetime

def my_score_this_month(request):
    n = datetime.datetime.now()

    my_blogs = []
    my_score = 0
    #if request.user and request.user.is_authenticated():
    #    my_blogs = [x.blog_at_price.blog for x in UserBlog.objects.filter(user=request.user)]
    #    scores = request.user.usermonthscore_set.filter(month=n.month, year=n.year)
    #    if len(scores) > 0:
    #        my_score = scores[0].score
    if request.user and request.user.is_authenticated():
        my_score = Score.objects.filter(user2score__user=request.user,
            month=n.month, year=n.year).aggregate(Sum("value"))["value__sum"]
        my_blogs = Blog.objects.filter(user2blog__user=request.user)
    return {"my_score_this_month": my_score, "my_blogs": my_blogs}