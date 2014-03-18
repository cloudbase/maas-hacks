import time
import requests
import StringIO
import gzip
import uuid
import getopt
import sys
import re
import tarfile
import json
import posixpath

from oauth import oauth


MAAS_URL = "http://192.168.209.134:5240"

def get_oauth_header(url, oauth_data=None):
    if oauth_data:
        oauth_consumer_secret = ""
        oauth_consumer_key = oauth_data[2]
        oauth_token_key = oauth_data[0]
        oauth_token_secret = oauth_data[1]

        consumer = oauth.OAuthConsumer(oauth_consumer_key, oauth_consumer_secret)
        token = oauth.OAuthToken(oauth_token_key, oauth_token_secret)

        p = { 'oauth_version': "1.0",
                  'oauth_nonce': oauth.generate_nonce(),
                  'oauth_timestamp': int(time.time()),
                  'oauth_token': token.key,
                  'oauth_consumer_key': consumer.key,
        }

        req = oauth.OAuthRequest(http_url=url, parameters=p)
        req.sign_request(oauth.OAuthSignatureMethod_PLAINTEXT(), consumer,
                         token)
        return req.to_header()


def do_get(url, oauth_data=None):
    r = requests.get(url, headers=get_oauth_header(url, oauth_data))
    r.raise_for_status()
    return r


def do_post(url, data=None, oauth_data=None, multipart_form=None, content_type=None):
    headers = get_oauth_header(url, oauth_data)
    if content_type:
        if headers:
            headers.update({"content-type": content_type})
        else:
            headers = content_type

    r = requests.post(url, data=data, files=multipart_form,
                      headers=headers)
    r.raise_for_status()
    return r

def node_declaration():
    do_get("%s/metadata/latest/enlist-preseed/?op=get_enlist_preseed" %
           MAAS_URL)
    do_get("%s/metadata/enlist/2012-03-01/meta-data/instance-id" % MAAS_URL)
    do_get("%s/metadata/enlist/2012-03-01/meta-data/local-hostname" % MAAS_URL)
    do_get("%s/metadata/enlist/2012-03-01/meta-data/public-keys" % MAAS_URL)
    do_get("%s/metadata/enlist/2012-03-01/user-data" % MAAS_URL)

    hostname = "%s.maas" % uuid.uuid4()
    mac_address = "00:50:56:28:d4:a9"

    data = { "op": "new", "autodetect_nodegroup": "1",
             "hostname":  hostname, "architecture": "amd64",
             "subarchitecture": "generic", "power_type": "",
             "mac_addresses" : mac_address}

    do_post("%s/api/1.0/nodes/" % MAAS_URL, data)


def get_maas_preseed_conn_data(preeseed_data):
    maas_url = None
    oauth_token_key = None
    oauth_token_secret = None
    oauth_consumer_key = None

    for l in preeseed_data.split("\n"):
        m = re.match(r"^\s+MAAS:\s+{consumer_key:\s+([^,]+),\s+metadata_url:\s+'([^']+)',\s*$", l)
        if m:
            oauth_consumer_key, maas_url = m.groups()
        m = re.match(r"^\s+token_key:\s+([^,]+),\s+token_secret:\s+([^}]+)}\s*$", l)
        if m:
            oauth_token_key, oauth_token_secret = m.groups()
        m = re.match(
            r"^cloud-init\s+cloud-init/maas-metadata-url\s+string\s+(.+)$", l)
        if m:
            maas_url = m.groups()[0]
        m = re.match(r"^cloud-init\s+cloud-init/maas-metadata-credentials\s+"
                     "string\s+oauth_token_key=([^&]+)&oauth_token_secret="
                     "([^&]+)&oauth_consumer_key=(.+)$", l)
        if m:
            (oauth_token_key,
             oauth_token_secret, oauth_consumer_key) = m.groups()

    if not oauth_token_key or not maas_url:
        raise Exception("Preseed data parsing error")

    return (maas_url, (oauth_token_key, oauth_token_secret,
                       oauth_consumer_key))


def node_commissioning(node_system_id):
    url = ("%(url)s/metadata/latest/by-id/%(system_id)s/?op=get_preseed" %
           {"url": MAAS_URL, "system_id": node_system_id})
    preeseed_data = do_get(url).text

    maas_url, oauth_data = get_maas_preseed_conn_data(preeseed_data)

    do_get("%s/2012-03-01/meta-data/instance-id" % maas_url, oauth_data)
    do_get("%s/2012-03-01/meta-data/local-hostname" % maas_url, oauth_data)
    do_get("%s/2012-03-01/meta-data/public-keys" % maas_url, oauth_data)
    do_get("%s/2012-03-01/user-data" % maas_url, oauth_data)

    r = do_get("%s/2012-03-01/maas-commissioning-scripts" % maas_url, oauth_data)
    t = tarfile.open(fileobj=StringIO.StringIO(r.content), mode="r")
    script_names = [posixpath.basename(n) for n in t.getnames()]
    tot_steps = len(script_names)

    step = 0
    for script_name in script_names:
        step += 1

        print script_name

        body = """
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="status";

WORKING
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="error";

starting %(script_name)s [%(step)s/%(tot_steps)s]
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="op";

signal
--a920db6e9cc74db4ba381d09d93f7110--
""" % {"script_name": script_name, "step": step,
       "tot_steps": tot_steps, "err_code": 0}

        body = body.replace('\n', '\r\n')

        # Cannot use request's "files" parameter as it adds "filename" in the content-disposition
        print do_post("%s/2012-03-01/" % maas_url, data=body,
                      oauth_data=oauth_data,
                      content_type="multipart/form-data; "
                      "boundary=a920db6e9cc74db4ba381d09d93f7110").text

        body = """
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="status";

WORKING
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="script_result"

%(err_code)s
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="error";

finished %(script_name)s [%(step)s/%(tot_steps)s]: %(err_code)s
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="op";

signal
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="%(script_name)s.out"; filename="%(script_name)s.out"
Content-Type: application/octet-stream

<?xml version="1.0" encoding="UTF-8"?>
<lldp label="LLDP neighbors"/>

--a920db6e9cc74db4ba381d09d93f7110--
""" % {"script_name": script_name, "step": step,
       "tot_steps": tot_steps, "err_code": 0,
       "script_output": uuid.uuid4()}

        body = body.replace('\n', '\r\n')

        # Cannot use request's "files" parameter as it adds "filename" in the content-disposition
        print do_post("%s/2012-03-01/" % maas_url, data=body,
                      oauth_data=oauth_data,
                      content_type="multipart/form-data; "
                      "boundary=a920db6e9cc74db4ba381d09d93f7110").text


    body = """
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="status";

OK
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="error";

finished [%(step)s/%(tot_steps)s]
--a920db6e9cc74db4ba381d09d93f7110
Content-Disposition: form-data; name="op";

signal
--a920db6e9cc74db4ba381d09d93f7110--
""" % {"step": step, "tot_steps": tot_steps}

    body = body.replace('\n', '\r\n')

    # Cannot use request's "files" parameter as it adds "filename" in the content-disposition
    print do_post("%s/2012-03-01/" % maas_url, data=body,
                  oauth_data=oauth_data,
                  content_type="multipart/form-data; "
                  "boundary=a920db6e9cc74db4ba381d09d93f7110").text


opts, args = getopt.getopt(sys.argv[1:], "dcn:")

commission = False

for opt, arg in opts:
    if opt == "-d":
        node_declaration()
        break
    elif opt == "-c":
        commission = True
    elif opt == "-n":
        node_system_id = arg

if commission:
    node_commissioning(node_system_id)



