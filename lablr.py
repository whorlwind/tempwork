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
#create redcap connection
project = Project(creds.rcp_url,creds.rcp_key)


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
    #connect to mysql uid database, get last uid, add new uids
    sqlsession=sessionmaker(bind=engine)()
    cursor=engine.connect()
    metadata=MetaData(engine)
    uids=Table('uid_db',metadata,autoload=True)
    lastuid=sqlsession.query(uids).order_by('-uid').first()
    lastuid=int(lastuid[0])
    numbertoadd=number
    newuids=tuple(range(lastuid+1,lastuid+numbertoadd+1))
    for item in newuids:
        ins=uids.insert().values(uid=item)
        cursor.execute(ins)   
    sqlsession.commit()
    return newuids
    
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
        session['uid']=" "
        session['sessionid']=random.randint(1000000,99000000)
        session['imagepath']="static/images/"+str(session['sessionid'])+".jpg"
        return render_template('addnew.html',session=session)
    if request.method=='POST':
        
        action=request.form['submit']
        session['uid']=request.form['uidentry']
        session['cell']=request.form['celltype']
        session['stain']=request.form['staintype']
        session['patient']=request.form['patient']
        if action=='Get Slide Image':
            i=Image("http://10.10.0.25:8080/photoaf.jpg").getPIL()
            label=i.crop((930,290,1130,490))
            label=label.rotate(180)
            
            label.save(session['imagepath'])
            session['showimage']=True
            return render_template('addnew.html',session=session)
        if action=='Scan Barcode':
            bar=Image("http://10.10.0.25:8080/photoaf.jpg").getPIL().convert('L')
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
        if action=='Add Slide':
           
            if session['cell'] and session['stain'] and session['patient']:
                complete=1
            else:
                complete=0
            
            record = {'uid': session['uid'] ,'cell': session['cell'], 
                      'stain': session['stain'],'patient': session['patient'],
                      'my_first_instrument_complete':complete}
            
            testforexist=project.export_records(records=[session['uid']])
            print request.form.get('confirm')
            if testforexist and (request.form.get('confirm') == None):
                session['exist']=True
                session['existpatient']=str(testforexist[0].get('patient'))
                session['existstain']=str(testforexist[0].get('stain'))
                session['existcell']=str(testforexist[0].get('cell'))
                #! do something to catch uid already in use !
                return render_template('addnew.html',session=session)
            uid=project.import_records([record],return_content='ids')[0]
            with open(session['imagepath'],'rb') as fobj:
                project.import_file(uid,'slide_image','slide_image.jpg',fobj)
            if os.path.isfile(session['imagepath']):
                os.remove(session['imagepath'])
                  
            session.clear()
            return redirect('/addnew')
        if action=='Return':
               
            session.clear()
            return redirect(url_for('index'))
            
        
    
app.secret_key=creds.flask_key
if __name__=='__main__':
    app.run()


