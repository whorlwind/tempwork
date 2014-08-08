import os
from flask import Flask, render_template, request, url_for, jsonify
from sqlalchemy.engine import create_engine
import barcode
from barcode.writer import ImageWriter
import platform
import StringIO



ean= barcode.get('ean13','4213213', writer=ImageWriter())
i=StringIO.StringIO()
i=StringIO.StringIO(i.getvalue())
ean.write(i)
i.seek(0)

if platform.system()=='Linux':
                import subprocess
                lpr=subprocess.Popen("/usr/bin/lpr",stdin=subprocess.PIPE)
                lpr.stdin.write(i.getvalue())