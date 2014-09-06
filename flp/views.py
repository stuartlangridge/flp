from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Blog, Score, Post, User2Score, User2Blog
from django.conf import settings
import datetime, re, os
from django.db import connection
from django.template.context import RequestContext
from django.db.models import Q, Max, Sum
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
import flp.common
from django.core.urlresolvers import reverse

def fetchfeeds(request):
    secret = request.GET.get("secret")
    if secret and secret == os.environ.get("FETCHFEEDS_SECRET"):
        from django.core.management import call_command
        call_command('fetchfeeds')
        return HttpResponse("done.")
    return HttpResponse("you fail.")

def index(request):
    now = datetime.datetime.now()
    
    # Calculate top blogs ever
    cursor = connection.cursor()
    cursor.execute("""select avg(sq.total),sq.blog_id,sq.name from (
        select p.blog_id,b.name,s.month,s.year,sum(value) as total 
        from flp_score s inner join flp_post p on s.post_id=p.id 
        inner join flp_blog b on p.blog_id=b.id group by p.blog_id, 
        b.name, s.month, s.year
        ) sq group by sq.blog_id, sq.name order by avg(sq.total) desc;""")
    top_blogs_ever = cursor.fetchall()[:5]

    cursor.execute("""select u.id, u.username, s.month, sum(s.value) as total
        from auth_user u 
        left outer join flp_user2score us on u.id=us.user_id 
        left outer join flp_score s on us.score_id=s.id
        where s.month = %s or s.month is null
        group by u.id, u.username, s.month order by total desc""", [now.month])
    highest_scorers_this_month = sorted(cursor.fetchall(), 
        cmp=lambda b,a:cmp(a[3],b[3]))[:5]

    authors = dict([
        (
            (p.author,p.blog.id), 
            {"author": p.author, "blogid": p.blog.id, "blogname": p.blog.name}
        )
        for p in Post.objects.all().order_by("author") if p.author]).values()
    return render(request, "index.html", {
        "blogs": Blog.objects.all().order_by("name"),
        "top_blogs_this_month": Score.objects.filter(month=now.month,year=now.year
            ).values("post__blog__name", "post__blog__id").annotate(
            total=Sum("value")).order_by("-total")[:5],
        "top_blogs_ever": top_blogs_ever,
        "highest_scorers_this_month": highest_scorers_this_month,
        "budget": settings.BUDGET,
        "authors": authors,
        "recent_scores": Score.objects.all().order_by("-created_date")[:5]
    })

def blog(request, blogdbid):
    blog = get_object_or_404(Blog, pk=blogdbid)

    now = datetime.datetime.now()
    all_scores_by_date = Score.objects.filter(post__in=blog.post_set.all()).order_by("-created_date")
    subscribers = User2Blog.objects.filter(blog=blog)
    total_score_this_month = Score.objects.filter(post__blog=blog, month=now.month,
        year=now.year).aggregate(total=Sum("value"))["total"]
    if not total_score_this_month: total_score_this_month = 0

    return render(request, "blog.html", {"blog": blog, 
        "all_scores_by_date": all_scores_by_date,
        "subscribers": subscribers,
        "total_score_this_month": total_score_this_month})

def user(request, username):
    thisuser = get_object_or_404(User, username=username)

    now = datetime.datetime.now()
    thismonthscore = Score.objects.filter(user2score__user=thisuser,
        month=now.month, year=now.year).aggregate(total=Sum("value"))
    thismonthscore["month"] = now.month
    thismonthscore["year"] = now.year
    thismonthscore["position"] = 0

    # Calculate rank and score for all months
    cursor = connection.cursor()
    cursor.execute("""select count(*) as rank, sq1.month, sq1.year, sq2.ts as score
    from (
        select u.id, s.month, s.year, sum(s.value) as ts 
        from auth_user u 
        inner join flp_user2score us on u.id = us.user_id
        inner join flp_score s on s.id = us.score_id
        group by u.id, s.month, s.year
    ) sq1 inner join (
        select u.id, s.month, s.year, sum(s.value) as ts 
        from auth_user u 
        inner join flp_user2score us on u.id = us.user_id
        inner join flp_score s on s.id = us.score_id
        where u.id = %s
        group by u.id, s.month, s.year
    ) sq2 on sq1.month = sq2.month and sq1.year = sq2.year
        where sq1.ts >= sq2.ts
        group by sq1.month, sq1.year, sq2.ts
        order by sq1.year desc, sq1.month desc;
    """, [thisuser.id])
    monthscores = cursor.fetchall()

    for m in monthscores:
        if m[1] == now.month and m[2] == now.year:
            thismonthscore["position"] = m[0]

    return render(request, "user.html", {"thisuser": thisuser, 
        "thismonthscore": thismonthscore, "monthscores": monthscores,
        "individual_scores": Score.objects.filter(user2score__user=thisuser,
            month=now.month, year=now.year),
        "userblogs": Blog.objects.filter(user2blog__user=thisuser)})

def signed_in(request):
    myblogs = User2Blog.objects.filter(user=request.user)
    if myblogs.count() == 0:
        return redirect("my-blogs")
    return redirect("index")

@login_required
def my_blogs(request):
    budget = settings.BUDGET
    errors = []

    # Calculate top blogs ever
    cursor = connection.cursor()
    cursor.execute("""select avg(sq.total),sq.blog_id,sq.name from (
        select p.blog_id,b.name,s.month,s.year,sum(value) as total 
        from flp_score s inner join flp_post p on s.post_id=p.id 
        inner join flp_blog b on p.blog_id=b.id group by p.blog_id, 
        b.name, s.month, s.year
        ) sq group by sq.blog_id, sq.name order by avg(sq.total) desc;""")
    average_month_scores_by_blog = dict([(x[1], x[0]) for x in cursor.fetchall()])

    mybloglist = Blog.objects.filter(user2blog__user=request.user).values(
        "id", "user2blog__price")
    mybloglist = dict([(x["id"], x) for x in mybloglist])
    # get list of all blogs
    bloglist = []
    for blog in Blog.objects.all().values("price", "name", "id"):
        if blog["id"] in mybloglist:
            blog["my_price"] = mybloglist[blog["id"]]["user2blog__price"]
        else:
            blog["my_price"] = None
        blog["average_month_score"] = average_month_scores_by_blog.get(blog["id"], 0)
        bloglist.append(blog)
    blogdict = dict([(x["id"],x) for x in bloglist])

    if request.method == "POST":
        # may fail but will just throw error
        try:
            chosen = [int(re.match(r'^chosen_([0-9]+)$', x).groups()[0]) 
                for x in request.POST.keys()
                if re.match(r'^chosen_([0-9]+)$', x)]
        except:
            errors.append("Something went wrong. Sorry.")
        else:
            if len(chosen) != 5: errors.append("You must choose five blogs")
            
            to_add = []
            to_leave_alone = []

            totalspent = 0
            for blogid in chosen:
                if errors: continue

                if blogid in mybloglist:
                    # we already had this blog. So leave it alone
                    to_leave_alone.append(blogid)
                    totalspent += mybloglist[blogid]["user2blog__price"]
                    del mybloglist[blogid]
                else:
                    # we did not already have this blog
                    blogobj = blogdict.get(blogid)
                    if not blogobj:
                        errors.append("There was an internal problem (a blog did not exist). Sorry.")
                        continue
                    to_add.append({"blog": blogid, "price": blogobj["price"]})
                    totalspent += blogobj["price"]
            to_delete = mybloglist.keys()

            if not errors:
                if totalspent > budget:
                    errors.append("You can't spend more than the budget!")
                else:
                    created_at = datetime.datetime.now()
                    existing_user_blogs = User2Blog.objects.filter(user=request.user)
                    backdate_scores = False
                    if existing_user_blogs.count() == 0:
                        backdate_scores = True
                        # this is the first time they've selected any blogs at all
                        # So pretend they created them right at the beginning of the month
                        # so that they have a score now.
                        created_at = created_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                    msg = []
                    for blogid in to_delete:
                        if errors: continue
                        try:
                            ub = User2Blog.objects.get(user=request.user, blog__id=blogid)
                        except User2Blog.DoesNotExist:
                            errors.append("There was an internal problem (a blog could not be found). Sorry.")
                            continue
                        ub.delete()
                        msg.append("deleted %s" % blogid)

                    for blogd in to_add:
                        if errors: continue
                        try:
                            blog = Blog.objects.get(id=blogd["blog"])
                        except Blog.DoesNotExist:
                            errors.append("There was an internal problem (a blog could not be found). Sorry.")
                            continue
                        User2Blog(user=request.user, blog=blog, 
                            price=blogd["price"], created_at=created_at).save()
                        msg.append("added %s" % blogd["blog"])

                    if backdate_scores:
                        # allocate scores for the chosen blogs that we backdated
                        for blogd in to_add:
                            scores = Score.objects.filter(month=created_at.month,
                                year=created_at.year, post__blog__id=blogd["blog"])
                            for score in scores:
                                score = User2Score(score=score, user=request.user)
                                score.save()
                                msg.append("added score %s" % (score,))

                    return redirect("user", request.user.username)


    return render(request, "my_blogs.html", {"bloglist": bloglist,
        "budget": budget, "errors": errors})
