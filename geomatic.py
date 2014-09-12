#!/usr/bin/python

# This is the main script for running GDAL and OGR command line utilities.  It should 
# always remain relatively simple, as it's only an entrypoint.  
#
# This is implemented to the spec required by django_docker_processes and should be
# considered an example of "how to do it"

import sh
import requests
import os
import json
import sys
import zipfile
import tempfile

# input parameters as environment variables, a la Docker
params = os.environ.get('PARAMS', None)
params_url = os.environ.get('PARAMS_URL', None)
response_url = os.environ['RESPONSE_URL']
abort_url = os.environ['ABORT_URL']
source_data_url = os.environ['SRC_URL']
source_data_filename = os.environ['SRC_FILENAME']
unzip_source = os.environ.get('UNZIP_SRC', False)
assign_srs = os.environ.get('ASSIGN_SRS', None)

GDAL_COMMANDS = { 
    'gdal2tiles.py',
    'gdal2xyz.py',
    'gdal_auth.py',
    'gdal_calc.py',
    'gdal_contour',
    'gdal_contrast_stretch',
    'gdal_dem2rgb',
    'gdal_edit.py',
    'gdal_fillnodata.py',
    'gdal_get_projected_bounds',
    'gdal_grid',
    'gdal_landsat_pansharp',
    'gdal_list_corners',
    'gdal_make_ndv_mask',
    'gdal_merge.py',
    'gdal_merge_simple',
    'gdal_merge_vrt',
    'gdal_polygonize.py',
    'gdal_proximity.py',
    'gdal_rasterize',
    'gdal_raw2geotiff',
    'gdal_retile.py',
    'gdal_sieve.py',
    'gdal_trace_outline',
    'gdal_translate',
    'gdal_wkt_to_mask',
    'gdaladdo',
    'gdalbuildvrt',
    'gdalchksum.py',
    'gdaldem',
    'gdalenhance',
    'gdalident.py',
    'gdalimport.py',
    'gdalinfo',
    'gdallocationinfo',
    'gdalmanage',
    'gdalmove.py',
    'gdalserver',
    'gdalsrsinfo',
    'gdaltindex',
    'gdaltransform',
    'gdalwarp',
    'ogr2ogr',
    'ogrinfo',
    'ogrtindex',
    'cs2cs',
}   


# assume our params are JSON. If we don't have params, then try to grab from a URL
if params:
    try:
        params = json.loads(params)
    except json.JSONDecodeError as e:
        requests.post(abort_url, data={
            'error_text': str(e)
        })
        r.raise_for_status() # in case the abort URL is effed
        sys.exit(1)
else:
    try:
        params = requests.get(params_url).json()
    except requests.ConnectionError as e:
        requests.post(abort_url, data={
            'error_text': str(e)
        })
        r.raise_for_status() # in case the abort URL is effed
        sys.exit(1)
    except json.JSONDecodeError as e:
        requests.post(abort_url, data={
            'error_text': str(e)
        })
        r.raise_for_status() # in case the abort URL is effed
        sys.exit(1)
    except ValueError as e:
        requests.post(abort_url, data={
            'error_text': str(e)
        })
        r.raise_for_status() # in case the abort URL is effed
        sys.exit(1)
    
# now that we have our params, let's do cool stuff with them
command = params['command']
args = params.get('args', [])
kwargs = params.get('kwargs', {})

if command not in GDAL_COMMANDS:
    requests.post(abort_url, data={
        'error_text': "{command} is not a valid GDAL or OGR command".format(command=command)
    })

# okay, we have a valid command and some params.  we're sure we're going to run this thing
# so let's get the data
tmpd = tempfile.mkdtmp()
os.chroot(tmpd)
source_data_filename = os.path.split(source_data_filename)[-1]

try:
    r = requests.get(source_data_url)
    with open(source_data_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size):
            fd.write(chunk)
except requests.ConnectionError as e:
    requests.post(abort_url, data={
        'error_text': str(e)
    })
    r.raise_for_status() # in case the abort URL is effed
    sys.exit(1)     

files_to_delete = [source_data_filename]
if unzip_source:
    zf = zipfile.ZipFile(source_data_filename)
    files_to_delete.extend(zf.namelist())
    zf.extractall()

if assign_srs:
    if assign_srs.lower() == 'epsg:4326':
        source_data_prj_name = source_data_filename.split('.')[0]
        with open(source_data_prj_name, 'w') as prj:
            prj.write(open('4326.prj').read())
    elif assign_srs.lower() == 'epsg:3857' or assign_src.lower() == 'epsg:900913':
        with open(source_data_prj_name, 'w') as prj:
            prj.write(open('3857.prj').read())
    elif assign_srs.lower().startswith('epsg'):
        code = assign_srs.split(':')[-1]
        with open(source_data_prj_name, 'w') as prj:
            prj.write(requests.get("http://spatialreference.org/ref/epsg/{code}/prj/".format(code=code)).text)
    else:
        with open(source_data_prj_name, 'w') as prj:
            prj.write(assign_srs)



cmd = sh.Command("/usr/bin/{command}".format(command=command)
cmd(*args, _out='stdout.txt', _err='stdout.err', **kwargs)

# clean up source files, because whatever's left in the directory we're going to post
for f in files_to_delete:
    os.unlink(f) 

files_to_post = []
for f in os.listdir('.'):
    if os.isdir(f):
        zfname = f.split('.')[0] + '.zip'
        sh.zip('-r', zfname, f)
        files_to_post.append(zfname)
    else:
        files_to_post.append(f)

files_to_post = {"file_{n}".format(n=n): (f, open(f)) for n, f in enumerate(files_to_post)}
requests.post(response_url, files=files_to_post)

# if for some reason the results URL doesn't work, let's say something
try:
    r.raise_for_status()
except Exception as e:
    requests.post(abort_url, data={
        'error_text': str(e)
    })
    r.raise_for_status() # in case the abort URL is effed
    sys.exit(1) 
    
# we don't bother deleting the output because the container will be deleted when the 
# process is finished
