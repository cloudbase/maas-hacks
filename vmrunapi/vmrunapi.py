#!/usr/bin/python
import flask
import os
import re
import subprocess
import sys

if sys.platform == 'win32':
    from win32com.shell import shell
    from win32com.shell import shellcon

app = flask.Flask(__name__)

STARTED = "started"
STOPPED = "stopped"


def _get_matching_vmx_path(path, mac_address):
    mac_address_re = re.compile(r'^ethernet(\d+)\.address(\s*)=(\s*)\"%s\"$' %
                                mac_address.upper())

    for root, dirs, file_names in os.walk(path):
        for file_name in file_names:
            if os.path.splitext(file_name)[1].lower() == '.vmx':
                vmx_path = os.path.join(root, file_name)
                with open(vmx_path, 'rb') as f:
                    for l in f:
                        if mac_address_re.match(l):
                            return vmx_path


def _get_vmx_base_path():
    if sys.platform == 'darwin':
        return os.path.expanduser("~/Documents/Virtual Machines")
    elif sys.platform == 'win32':
        documents_dir = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL,
                                              None, 0)
        return os.path.join(documents_dir, "Virtual Machines")
    else:
        return os.path.expanduser("~/vmware")


def _get_vmrun():
    if sys.platform == 'darwin':
        return ("/Applications/VMware Fusion.app/Contents/Library/vmrun",
                "fusion")
    else:
        # Make sure to have vmrun in the PATH
        return ("vmrun", "ws")


def _execute_process(args):
    p = subprocess.Popen(args,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=False)
    (out, err) = p.communicate()
    return (out, err, p.returncode)


def _exec_vmrun_cmd(cmd, vmx_path=None):
    (vmrun_path, vmrun_type) = _get_vmrun()

    args = [vmrun_path, "-T", vmrun_type, cmd]
    if vmx_path:
        args.append(vmx_path)

    (out, err, exit_code) = _execute_process(args)

    if exit_code:
        raise Exception("vmrun failed: %s" % out)

    return out


@app.route('/vmrun/vm/find_by_mac_address/<string:mac_address>',
           methods = ['GET'])
def get_vmx_path_bymac_address(mac_address):
    base_path = _get_vmx_base_path()
    vmx_path = _get_matching_vmx_path(base_path, mac_address)
    if not vmx_path:
        flask.  abort(404)
    else:
        return vmx_path


def _get_json_vmx_path():
    if not flask.request.json:
        flask.abort(400)

    vmx_path = flask.request.json.get('vmx_path')
    if not vmx_path:
        flask.abort(400)

    if not os.path.exists(vmx_path):
        flask.abort(404)

    return vmx_path


@app.route('/vmrun/vm/start', methods = ['POST'])
def start_vm():
    vmx_path = _get_json_vmx_path()
    _exec_vmrun_cmd("start", vmx_path)
    return STARTED


@app.route('/vmrun/vm/stop', methods = ['POST'])
def stop_vm():
    vmx_path = _get_json_vmx_path()
    _exec_vmrun_cmd("stop", vmx_path)
    return STARTED


@app.route('/vmrun/vm/status', methods = ['POST'])
def get_vm_status():
    status = STOPPED

    vmx_path = _get_json_vmx_path()

    running_vmx_paths = _exec_vmrun_cmd("list").split("\n")[1:-1]
    for running_vmx_path in running_vmx_paths:
        if vmx_path == running_vmx_path:
            status = STARTED
            break

    return status


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=6000, debug = True)
