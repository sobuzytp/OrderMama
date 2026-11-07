import io,json
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import Http404,HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_POST
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from django.conf import settings
from .models import *
def home(request): return render(request,"home.html")
def menu(request,slug,number):
 r=get_object_or_404(Restaurant,slug=slug,is_active=True); table=get_object_or_404(DiningTable,restaurant=r,number=number,is_active=True)
 if request.method=="POST":
  name=request.POST.get("name","").strip(); phone=request.POST.get("phone","").strip()
  try: rows=json.loads(request.POST.get("items","[]"))
  except ValueError: rows=[]
  if not name or len(phone)<7 or not rows: return HttpResponse("নাম, মোবাইল ও খাবার নির্বাচন করুন",status=400)
  with transaction.atomic():
   o=Order.objects.create(restaurant=r,table=table,customer_name=name,customer_phone=phone); total=Decimal("0")
   for row in rows[:30]:
    item=get_object_or_404(MenuItem,pk=row["id"],restaurant=r,is_available=True); qty=max(1,min(int(row.get("qty",1)),20))
    OrderItem.objects.create(order=o,menu_item=item,item_name=item.name,unit_price=item.price,quantity=qty,note=str(row.get("note",""))[:250]); total+=item.price*qty
   o.total=total; o.save()
  return redirect("track",slug=slug,token=o.public_token)
 return render(request,"menu.html",{"restaurant":r,"table":table,"categories":r.categories.filter(is_active=True).prefetch_related("items")})
def track(request,slug,token):
 o=get_object_or_404(Order,restaurant__slug=slug,public_token=token); return render(request,"track.html",{"order":o})
@require_POST
def service(request,slug,number,kind):
 if kind not in ["waiter","bill"]: raise Http404
 r=get_object_or_404(Restaurant,slug=slug); t=get_object_or_404(DiningTable,restaurant=r,number=number); ServiceRequest.objects.create(restaurant=r,table=t,kind=kind); return redirect("menu",slug=slug,number=number)
def member(user,r): return RestaurantMembership.objects.filter(user=user,restaurant=r).first()
@login_required
def dashboard(request,slug):
 r=get_object_or_404(Restaurant,slug=slug); m=member(request.user,r)
 if not(request.user.is_staff or (m and m.role in ["owner","manager","cashier"])): raise Http404
 from django.utils.timezone import localdate
 today=r.orders.filter(created_at__date=localdate())
 return render(request,"dashboard.html",{"restaurant":r,"orders":r.orders.all()[:20],"count":today.count(),"sales":today.filter(status__in=["served","paid"]).aggregate(v=Sum("total"))["v"] or 0})
@login_required
def kot(request,slug):
 r=get_object_or_404(Restaurant,slug=slug); m=member(request.user,r)
 if not(request.user.is_staff or (m and m.role in ["owner","manager","cashier","kitchen"])): raise Http404
 return render(request,"kot.html",{"restaurant":r,"orders":r.orders.filter(status__in=["pending","accepted","preparing","ready"]).prefetch_related("items")})
@login_required
@require_POST
def status(request,slug,pk):
 r=get_object_or_404(Restaurant,slug=slug); m=member(request.user,r)
 if not(request.user.is_staff or (m and m.role in ["owner","manager","cashier","kitchen"])): raise Http404
 o=get_object_or_404(Order,pk=pk,restaurant=r); flow={"pending":["accepted","rejected"],"accepted":["preparing"],"preparing":["ready"],"ready":["served"],"served":["paid"]}; new=request.POST.get("status")
 if new in flow.get(o.status,[]): o.status=new; o.save()
 return redirect("kot",slug=slug)
@login_required
def qr_pdf(request,slug):
 r=get_object_or_404(Restaurant,slug=slug); m=member(request.user,r)
 if not(request.user.is_staff or (m and m.role in ["owner","manager"])): raise Http404
 b=io.BytesIO(); p=canvas.Canvas(b)
 for i,t in enumerate(r.tables.filter(is_active=True)):
  if i and i%4==0: p.showPage()
  img=qrcode.make(f"{settings.SITE_URL}/r/{slug}/table/{t.number}/"); q=io.BytesIO(); img.save(q,format="PNG"); q.seek(0); x=45+(i%2)*270; y=680-(i%4//2)*360
  p.drawImage(ImageReader(q),x,y,width=140,height=140); p.drawString(x,y-20,f"{r.name} - Table {t.number}")
 p.save(); b.seek(0); response=HttpResponse(b.getvalue(),content_type="application/pdf"); response["Content-Disposition"]=f'attachment; filename="{slug}-qr.pdf"'; return response
