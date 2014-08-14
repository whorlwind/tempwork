import os
from flask import *
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from flask.ext.bootstrap import Bootstrap
import barcode
from barcode.writer import ImageWriter
import platform
import StringIO
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing 
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from SimpleCV import Image
from redcap import Project, RedcapError
import time
import zbar
import creds
import random
import urllib2
import shutil
#create redcap connection
project = Project(creds.rcp_url,creds.rcp_key)
session_records={}
phone_ip='192.168.99.209'
app=Flask(__name__)
app.debug=True
Bootstrap(app)
engine=create_engine(creds.mysql_url)
#allows timestamp to be added to images, forces browser reload
app.jinja_env.globals.update(time=time)

@app.route('/',methods=['GET','POST'])
def index():
    data=""
    if request.method=='GET':        
        return render_template('index.html',data=data)
    elif request.method =='POST':
        action=request.form['submit']
        if action=='Print':
            number=request.form['number']
            try:
                number=int(number)
            except ValueError:
                return render_template('index.html',data=data)
            uids=adduids(number)
            printlabels(uids)
            return app.send_static_file('barcodes.pdf')


                    
               
def adduids(number):
    #connect to redcap database, get last uid, add new uid
    
    newuids=list()
    for i in range(number):
        uids=project.export_records(fields=['uid'])
        lastuid=int(uids[-1]['uid'])    
        newuid=str(lastuid+1)
        now=time.strftime('%Y-%m-%d %H:%M')
        added=int(project.import_records([{'uid':newuid,'uid_time':now}],
                                          return_content='ids')[0])
        newuids.append(added)
        project.export_records()
    return tuple(newuids)
    
def printlabels(uids):  
    #draw qr codes for uids to pdf file
    c = canvas.Canvas("static/barcodes.pdf", pagesize=(120,54))
    for each in uids:
        c.setFont("Helvetica-Bold",4)
        qr_code = qr.QrCodeWidget(str(each))
        bounds = qr_code.getBounds()
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        d = Drawing(0, 0, transform=[27./width,0,0,27./height,0,0])
        d.add(qr_code)
        c.saveState()
        c.rotate(-90)
        c.translate(0,85)
        c.drawCentredString(-39,0,str(each))
        c.restoreState()
        renderPDF.draw(d, c,58,25)
        c.showPage()
    c.save()
    return
    
    
@app.route('/addnew',methods=['GET','POST'])
def addnew():    
    
    if request.method=='GET': 
        session['showbarcode']=False
        session['showimage']=False
        session['sessionid']=random.randint(1000000,99000000)
        session['imagepath']="static/images/"+str(session['sessionid'])+".jpg"
        
        return render_template('addnew.html',session=session)
    if request.method=='POST':
        action=request.form['submit'] 
        for field in project.field_names:
            if field != 'slide_image':
                session[field]=request.form[field]
               
        if action=='Get Slide Image':
            i=Image(("http://"+phone_ip+":8080//photoaf.jpg")).getPIL()
            label=i.crop((930,290,1130,490))
            label=label.rotate(180)
            
            label.save(session['imagepath'])
            session['showimage']=True
            return render_template('addnew.html',session=session)
        if action=='Scan Barcode':
            bar=Image(("http://"+phone_ip+":8080/photoaf.jpg")).getPIL().convert('L')
            scanner = zbar.ImageScanner()
            scanner.parse_config('enable')
            width,height=bar.size
            raw = bar.tostring()
            image = zbar.Image(width, height, 'Y800', raw)
            if scanner.scan(image):
                for symbol in image:
                    session['uid']=symbol.data
            else:
                session['uid']="unrecognized, try again"   
            return render_template('addnew.html',session=session)
        if action=='Create UID':
            uid=adduids(1)
            session['uid']=uid[0]
            return render_template('addnew.html',session=session)
        if action=='Download Barcode':
            printlabels([session['uid'],])
            return app.send_static_file('barcodes.pdf')
        if action=='Add Slide':
           
#            if session['cell'] and session['stain'] and session['patient']:
#                complete=1
#            else:
#                complete=0
            record={}
            for field in project.field_names:
                if field != 'slide_image':
                    record[field]=session[field]
            record['slide_info_complete']=1
            
            testforexist=project.export_records(records=[session['uid']],raw_or_label='label')
            if (testforexist[0].get('slide_info_complete')!='Incomplete') and (request.form.get('confirm') == None):
                current=testforexist[0]
                session['exist']=True
                for field in project.field_names:
                    if field != 'slide_image':
                        session[field+'exist']=current[field]
                if current['stain']=='Other':
                    session['stainexist']=current['stain_other']
                return render_template('addnew.html',session=session)
            uid=project.import_records([record],return_content='ids')[0]
            with open(session['imagepath'],'rb') as fobj:
                project.import_file(uid,'slide_image','slide_image.jpg',fobj)
            try:
                os.remove(session['imagepath'])
            except:
                pass
            if request.form.get('keepinfo') == 'on':
                session['keepinfo']=True
                session['exist']=False
            else:
                session.clear()
            return redirect('/addnew')
        if action=='Return':
            try:
                os.remove(session['imagepath'])
            except:
                pass   
            session.clear()
            return redirect(url_for('index'))

@app.route('/browse',methods=['GET','POST'])
def browse():    
    session_records={} 
    if request.method=='GET': 
        session['sessionid']=random.randint(1000000,99000000)
        session['imagepath']="static/images/"+str(session['sessionid'])+"/"
        os.mkdir(str(session['imagepath']))
        return render_template('browse.html',session=session)
    if request.method=='POST':
        action=request.form['submit'] 
        session_records[str(session['sessionid'])]=project.export_records(raw_or_label='raw')
        if action=='Display Unverified':
            display_records=list([])
            for slide in session_records[str(session['sessionid'])]:
                if slide['slide_info_complete']=='1':
                    picture_data,headers=project.export_file(record=slide['uid'],field='slide_image')
                    with open(str(session['imagepath']+slide['uid']+".jpg"),'w+') as f:
                        f.write(picture_data)
                    display_records.append(slide)
            return render_template('browse.html',session=session,display_records=display_records)
        if action=='Commit Changes':
            verified_records=request.form.getlist('verified_records[]')
            changed_records=list()
            for record in verified_records:
                changedrecord={}
                for field in project.field_names:
                    if (field != 'slide_image') and (field != 'uid_time'):
                        changedrecord[field]=request.form[field+'_'+record]
                changed_records.append(changedrecord)
            project.import_records(changed_records)
            return render_template('browse.html',session=session)
        if action=='Return':
            try:
                shutil.rmtree(session['imagepath'])
            except OSError:
                pass   
            session.clear()
            return redirect(url_for('index'))

app.secret_key=creds.flask_key
if __name__=='__main__':
    app.run(host='170.140.61.50')


