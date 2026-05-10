"""
app.py — AI Smart Data Analyzer v2.0
All original routes preserved. New core modules wired in.
"""

import os, json, uuid, logging
from datetime import datetime

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, send_file)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np

from core.cleaner    import DataCleaner
from core.visualizer import DataVisualizer
from core.insights   import InsightEngine
from core.reporter   import ReportGenerator

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ai-smart-analyzer-dev-2024')
app.config.update(
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{os.path.join(BASE_DIR,"instance","analyzer.db")}',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=os.path.join(BASE_DIR,'static','uploads'),
    CHARTS_FOLDER=os.path.join(BASE_DIR,'static','charts'),
    MAX_CONTENT_LENGTH=32*1024*1024,
)
for d in [app.config['UPLOAD_FOLDER'], app.config['CHARTS_FOLDER'],
          os.path.join(BASE_DIR,'instance')]:
    os.makedirs(d, exist_ok=True)

db = SQLAlchemy(app)
ALLOWED = {'csv','xlsx','xls'}

class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    analyses      = db.relationship('Analysis', backref='user', lazy=True)

class Analysis(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename       = db.Column(db.String(256))
    original_rows  = db.Column(db.Integer)
    cleaned_rows   = db.Column(db.Integer)
    columns        = db.Column(db.Text)
    insights_json  = db.Column(db.Text)
    charts_json    = db.Column(db.Text)
    cleaning_json  = db.Column(db.Text)
    quality_before = db.Column(db.Float, default=0)
    quality_after  = db.Column(db.Float, default=0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

def allowed_file(fn): return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED
def login_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a,**kw):
        if 'user_id' not in session: return jsonify({'error':'Auth required'}),401
        return f(*a,**kw)
    return dec
def _load_df(fp):
    ext=fp.rsplit('.',1)[1].lower()
    return pd.read_csv(fp) if ext=='csv' else pd.read_excel(fp)
def _safe_json(o):
    if isinstance(o,(np.integer,)): return int(o)
    if isinstance(o,(np.floating,)): return float(o)
    if isinstance(o,(np.ndarray,)): return o.tolist()
    if isinstance(o,pd.Timestamp): return o.isoformat()
    raise TypeError(type(o))
def _stats(df):
    s={}
    for c in df.select_dtypes(include='number').columns:
        col=df[c].dropna()
        if len(col)==0: continue
        s[c]={'mean':round(float(col.mean()),2),'median':round(float(col.median()),2),
              'std':round(float(col.std()),2),'min':round(float(col.min()),2),
              'max':round(float(col.max()),2),'missing':int(df[c].isnull().sum()),
              'skew':round(float(col.skew()),2)}
    return s
def _export_csv(df, path):
    out=df.copy()
    for c in out.select_dtypes(include='datetime').columns:
        out[c]=out[c].dt.strftime('%Y-%m-%d')
    for c in out.select_dtypes(include=['float64','float32']).columns:
        out[c]=out[c].round(4)
    out.to_csv(path,index=False,na_rep='',encoding='utf-8-sig')

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else render_template('auth.html')

@app.route('/api/signup',methods=['POST'])
def signup():
    d=request.get_json() or {}
    name=d.get('name','').strip(); email=d.get('email','').strip().lower(); pw=d.get('password','')
    if not name or not email or not pw: return jsonify({'error':'All fields required'}),400
    if len(pw)<6: return jsonify({'error':'Password min 6 chars'}),400
    if User.query.filter_by(email=email).first(): return jsonify({'error':'Email already registered'}),400
    u=User(name=name,email=email,password_hash=generate_password_hash(pw))
    db.session.add(u); db.session.commit()
    session['user_id']=u.id; session['user_name']=u.name
    return jsonify({'success':True,'name':u.name})

@app.route('/api/login',methods=['POST'])
def login():
    d=request.get_json() or {}
    email=d.get('email','').strip().lower(); pw=d.get('password','')
    u=User.query.filter_by(email=email).first()
    if not u or not check_password_hash(u.password_hash,pw): return jsonify({'error':'Invalid credentials'}),401
    session['user_id']=u.id; session['user_name']=u.name
    return jsonify({'success':True,'name':u.name})

@app.route('/api/logout',methods=['POST'])
def logout(): session.clear(); return jsonify({'success':True})

@app.route('/api/me')
def me():
    if 'user_id' not in session: return jsonify({'authenticated':False})
    u=User.query.get(session['user_id'])
    if not u: session.clear(); return jsonify({'authenticated':False})
    return jsonify({'authenticated':True,'name':u.name,'email':u.email,
                    'analyses_count':Analysis.query.filter_by(user_id=u.id).count()})

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html') if 'user_id' in session else redirect(url_for('index'))

@app.route('/api/upload',methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files: return jsonify({'error':'No file'}),400
    f=request.files['file']
    if not f.filename or not allowed_file(f.filename): return jsonify({'error':'CSV or Excel only'}),400
    ext=f.filename.rsplit('.',1)[1].lower()
    fname=f'{uuid.uuid4().hex}.{ext}'
    fpath=os.path.join(app.config['UPLOAD_FOLDER'],fname)
    f.save(fpath)
    try: df=_load_df(fpath)
    except Exception as e: os.remove(fpath); return jsonify({'error':str(e)}),400
    if df.empty: return jsonify({'error':'File is empty'}),400
    session['current_file']=fpath
    session['original_filename']=secure_filename(f.filename)
    prev=df.head(6).fillna('').astype(str)
    return jsonify({'success':True,'rows':len(df),'columns':len(df.columns),
                    'column_names':list(df.columns),'preview':prev.to_dict(orient='records'),
                    'null_counts':{c:int(v) for c,v in df.isnull().sum().items()}})

@app.route('/api/analyze',methods=['POST'])
@login_required
def analyze():
    fp=session.get('current_file')
    if not fp or not os.path.exists(fp): return jsonify({'error':'Upload a file first'}),400
    try:
        df=_load_df(fp); orig=len(df)
        cleaner=DataCleaner(df); df_clean,cr=cleaner.clean()
        viz=DataVisualizer(df_clean,app.config['CHARTS_FOLDER'],schema=cr.get('schema',{}))
        charts=viz.generate_all_charts()
        engine=InsightEngine(df_clean,cr); insights=engine.generate_insights()
        a=Analysis(user_id=session['user_id'],
                   filename=session.get('original_filename','file.csv'),
                   original_rows=orig,cleaned_rows=len(df_clean),
                   columns=json.dumps(list(df_clean.columns)),
                   insights_json=json.dumps(insights,default=_safe_json),
                   charts_json=json.dumps(charts,default=_safe_json),
                   cleaning_json=json.dumps(cr,default=_safe_json),
                   quality_before=cr.get('quality_before',0),
                   quality_after=cr.get('quality_after',0))
        db.session.add(a); db.session.commit()
        session['analysis_id']=a.id
        cp=os.path.join(app.config['UPLOAD_FOLDER'],f'clean_{uuid.uuid4().hex}.csv')
        _export_csv(df_clean,cp); session['clean_file']=cp
        return jsonify({'success':True,'analysis_id':a.id,'original_rows':orig,
                        'cleaned_rows':len(df_clean),'columns':list(df_clean.columns),
                        'cleaning_report':json.loads(json.dumps(cr,default=_safe_json)),
                        'charts':charts,'insights':insights,
                        'stats':json.loads(json.dumps(_stats(df_clean),default=_safe_json)),
                        'quality_before':cr.get('quality_before',0),
                        'quality_after':cr.get('quality_after',0)})
    except Exception as e:
        logger.exception('Analysis failed')
        return jsonify({'error':f'Analysis failed: {str(e)}'}),500

@app.route('/api/download_report')
@login_required
def download_report():
    aid=session.get('analysis_id')
    if not aid: return jsonify({'error':'Run analysis first'}),400
    a=Analysis.query.get(aid)
    if not a or a.user_id!=session['user_id']: return jsonify({'error':'Not found'}),404
    try:
        fp=session.get('current_file'); df=_load_df(fp)
        cleaner=DataCleaner(df); df_clean,cr=cleaner.clean()
        r=ReportGenerator(df_clean,json.loads(a.insights_json),json.loads(a.charts_json),
                          json.loads(a.cleaning_json),a.filename,a.original_rows,a.cleaned_rows)
        pdf=r.generate()
        return send_file(pdf,as_attachment=True,
                         download_name=f'Report_{a.filename.rsplit(".",1)[0]}.pdf',
                         mimetype='application/pdf')
    except Exception as e:
        logger.exception('Report failed'); return jsonify({'error':str(e)}),500

@app.route('/api/download_clean_csv')
@login_required
def download_clean_csv():
    cp=session.get('clean_file')
    if not cp or not os.path.exists(cp): return jsonify({'error':'Run analysis first'}),400
    orig=session.get('original_filename','data.csv')
    return send_file(cp,as_attachment=True,
                     download_name=f'Cleaned_{orig.rsplit(".",1)[0]}.csv',mimetype='text/csv')

@app.route('/api/history')
@login_required
def history():
    rows=Analysis.query.filter_by(user_id=session['user_id'])\
         .order_by(Analysis.created_at.desc()).limit(15).all()
    return jsonify([{'id':a.id,'filename':a.filename,'original_rows':a.original_rows,
                     'cleaned_rows':a.cleaned_rows,'quality_before':a.quality_before,
                     'quality_after':a.quality_after,
                     'created_at':a.created_at.strftime('%d %b %Y, %H:%M')} for a in rows])

@app.route('/api/health')
def health(): return jsonify({'status':'ok','version':'2.0'})

if __name__=='__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True,port=5000)
