from flask import Flask, escape, request
import random 
from random import randint
import sqlite3
import os
from sqlite3 import Error
import json
from flask import send_from_directory


UPLOAD_FOLDER = os.getcwd()+os.path.sep+'files'
database = os.getcwd()+os.path.sep+"database.db"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(database)
    except Error as e:
        print(e)
    return conn

def create_table():
    conn = create_connection(database)
    c = conn.cursor()

    # Creating a new SQLite table with 1 column
    c.execute('CREATE TABLE IF NOT EXISTS tests( test_id INTEGER primary key AUTOINCREMENT, subject text, answer_keys text, submissions text);')
    
    c.execute('CREATE TABLE IF NOT EXISTS submissions( scantron_id INTEGER primary key AUTOINCREMENT, test_id INTEGER, scantron_url text, name text, subject text, score INTEGER, result text);')

    # Committing changes and closing the connection to the database file
    conn.commit()
    conn.close()
    
def is_int(val):
    try:
        num = int(val)
    except ValueError:
        return False
    return True

@app.route('/')
def hello():
    name = request.args.get("name", "World")
    return f'Hello, {escape(name)}!'
    
    
@app.route('/files/<dirname>/<filename>')
def uploaded_file(dirname,filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               dirname+"/"+filename)

@app.route('/api/tests', methods=['POST'])
def create_test():
    content = request.json
    subject = content["subject"]
    answer_keys =content["answer_keys"]
    #validation
    for key in answer_keys:
        if is_int(key)==False:
            return "Answer key invalid", 500
    answers= json.dumps(answer_keys)

    test=(subject,answers)
    create_table()
    conn=create_connection(database)
    sql = ''' INSERT INTO tests(subject,answer_keys)
              VALUES(?,?) '''
    cur = conn.cursor()
    cur.execute(sql, test)
    id=cur.lastrowid
    conn.commit()
    return {'test_id' : id ,"subject" : subject, "answer_keys": answer_keys, "submissions": [] },201


@app.route('/api/tests/<int:id>', methods=['GET'])
def get_test(id):
    conn=create_connection(database)
    sql = ''' SELECT * FROM tests WHERE test_id=?'''
    test=(id,)
    cur = conn.cursor()
    cur.execute(sql, test)

    rows = cur.fetchall()
    
    row=rows[0]
    subject=row[1]
    answer_keys=json.loads(row[2])
    
    #get submissions
    sql = ''' SELECT * FROM submissions WHERE test_id=?'''
    test=(id,)
    cur = conn.cursor()
    cur.execute(sql, test)

    rows = cur.fetchall()
    submissions=[]
    for row in rows:
        submission={}
        submission["scantron_id"]=row[0]
        submission['scantron_url']=row[2]
        submission['name']=row[3]
        submission['subject']=row[4]
        submission['score']=row[5]
        print(row[6])
        submission['result']=json.loads(row[6])
        submissions.append(submission)
    
    return {"test_id": id, "subject":row[1],"answer_keys": answer_keys, "submissions": submissions},200
    
@app.route('/api/tests/<int:id>/scantrons', methods=['POST'])
def upload_file(id):
    print("Uploading file")
    print(request)
    file = request.files['data']
    url_root = request.url_root
    # if user does not select file, browser also
    # submit an empty part without filename

    if file:
        print("file uploding to ")
        conn=create_connection(database)
        sql = ''' SELECT * FROM submissions WHERE test_id=?'''
        test=(id,)
        cur = conn.cursor()
        cur.execute(sql, test)
        submissions = cur.fetchall()
        
        filename = str(len(submissions)+1)+".json"
        dirname = os.path.join(app.config['UPLOAD_FOLDER'],str(id))
        try:
            os.mkdir(dirname)
        except FileExistsError:
            pass
        filePath=os.path.join(dirname, filename)
        print(filePath)
        print("FilePath:: "+filePath)
        file.save(filePath)
        
        f = open(filePath,'r') 
        data = json.load(f) 
  
        name=data['name']
        subject=data['subject']
        scores_submitted=data['answers']
  
        # Closing file 
        f.close()
        
        #get answer keys for the test
        sql = ''' SELECT * FROM tests WHERE test_id=?'''
        test=(id,)
        cur = conn.cursor()
        cur.execute(sql, test)

        rows = cur.fetchall()
        row=rows[0]
        answer_keys=json.loads(row[2])

        
        score=0
        result={}
        for key in scores_submitted:
            if key in answer_keys:
                if answer_keys[key]==scores_submitted[key]:
                    score=score+1
                t={}
                t['actual']=scores_submitted[key]
                t['expected']=answer_keys[key]
                result[key]=t
                
        #store in database
        
        conn=create_connection(database)
        sql = ''' INSERT INTO submissions(test_id,scantron_url,name,subject,score,result)
                  VALUES(?,?,?,?,?,?) '''
        cur = conn.cursor()
        
        scantron_url=url_root+"files/"+str(id)+"/"+filename
        submission=(id,scantron_url,name,subject,score,json.dumps(result))
        cur.execute(sql, submission)
        scanid=cur.lastrowid
        conn.commit()
        
        return {'scantron_id' : scanid ,"scantron_url" : scantron_url , "name": name, "subject": subject, "score": score, "result": result },201
