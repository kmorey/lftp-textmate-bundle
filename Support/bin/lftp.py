#!/usr/local/bin/python2.6
# TODO handle multiple file put,fetch
# TODO give configured sites a "name" for more user-friendly display
import sys
import os
import subprocess
import glob
import json
import optparse

class OptionParser (optparse.OptionParser):

    def check_required (self, opts):
		for opt in opts:
			option = self.get_option(opt)

			# Assumes the option's 'default' is set to None!
			val=getattr(self.values, option.dest)
			if val is not None and val != '': return
			
		self.error("One of the following options not supplied: %s" % ", ".join(opts))

DEBUG=True

def run():	
	parser=OptionParser()
	parser.add_option("-f", "--fetch", dest="fetch", help="full file path to download")
	parser.add_option("-p", "--put", dest="put", help="full file path to upload")
	parser.add_option("-m", "--mirror", dest="mirror", help="full file path to mirror")
	parser.add_option("-c", "--config", action="append", type="string", dest="config_dir", help="path to config dir")
	#parser.set_defaults(config_dir="config")

	(options, args) = parser.parse_args()
	
	parser.check_required(["-f", "-p", "-m"])

	print options.config_dir
	#if not os.path.isfile(options.filename): return (False, 'File does not exist.')

	#files=glob.glob('config/*.json')
	# config_path=getActualPath(options.config_dir)
	
	#if DEBUG: print "using config dir: "+config_path
	
	files=[]
	for config_path in options.config_dir:
		files.extend(glob.glob(os.path.join(getActualPath(config_path), "*.json")))
	
	readone=False
	msg=""
	sites={}
	for f in files:
		#load config
		fp=open(f)
		config=json.load(fp)
		fp.close()
	
		#error checking
		error=False
		if not 'host' in config: error=True
		if not 'user' in config: error=True
		if not 'pass' in config: error=True
		if not 'local_path' in config: error=True
		if not 'remote_path' in config: error=True
		if error:
			if DEBUG: print "invalid site"
			continue
	
		local_path=getActualPath(config['local_path'])
		relpath=os.path.relpath(getFilename(options), local_path)
		
		if DEBUG:
			print "Loaded %s...<br />" % (f)
			print getFilename(options)+"<br />"
			print local_path+"<br />"
			print "relpath=%s<br />" % relpath
			#print config
			print "<hr />"
		
		if relpath.find("..") == -1:
			sites[config['name']] = f
	
	if len(sites) == 0:
		growl('Failure', 'No sites found for the current file.')
		return (False, "No sites found for the current file.")
	
	if len(sites) == 1:
		sites=[sites.values()[0]]
	else:
		#prompt user to c	hoose
		sites_str='"'+'", "'.join(sites.keys())+'"'
		applescript=" -e 'tell app \"TextMate\"'"
		applescript+=" -e 'activate'"
		applescript+=" -e 'choose from list {"+sites_str+"} with title \"Multiple Site Configs Match\" with prompt \"Select the sites to use below:\" multiple selections allowed true'"
		applescript+=" -e 'end tell'"
	
		#print applescript
		sites=callApplescript(applescript, sites)
	
	for f in sites:
		#load config
		fp=open(f)
		config=json.load(fp)
		fp.close()
		
		if DEBUG: print "uploading to %s" % config['host']
		readone=True
		
		(cmd, success_msg) = getFtpCommand(options, config)
		if cmd is None: #error
			print "returning early!"
			growl('Failure', success_msg)
			return (False, success_msg)
		
		proc=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		(output, error)=proc.communicate(None)
		
		if DEBUG:
			print "<div style='background-color: #ccc; padding: 5px'><p style='font-weight: bold;'>lftp output</p>"
			print output.replace("\n", "<br />\n")
			print "</div>"
		
		success=proc.returncode
		#success=subprocess.call(cmd, shell=True)
		if success==0: 
			growl('Success', success_msg)
			# msg+=success_msg+"\n"
		else:
			growl('Failure', 'An error occurred in lftp.')
			# msg+="fail?\n"		
		
	if not readone:
		msg="No sites found for the current file."
		growl('Failure', msg)
	
	return (readone, msg)

def callApplescript(script, sites):
	
	out = []
	
	proc=subprocess.Popen("osascript "+script, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	(output, error)=proc.communicate(None)
	
	if proc.returncode == 0: 
		for key in output.strip().split(", "):
			out.append(sites[key])
	
	return out
	
def getActualPath(path):
	return os.path.realpath(os.path.expanduser(path))
	
def getFtpCommand(options, config):	
	#if DEBUG: print "Uploading '%s' to %s..." % (relpath, config['host'])
	
	fname = getFilename(options)
	local_path=getActualPath(config['local_path'])
	relpath = os.path.relpath(fname, local_path)
	filename = os.path.basename(fname)

	remote_path = os.path.join(config['remote_path'], relpath)
	local_path = os.path.join(local_path, relpath)
	
	#always make local path a folder
	if os.path.isfile(local_path):
		remote_path = os.path.dirname(remote_path)
		local_path = os.path.dirname(local_path)
	
	ftp_cmds = None
	success_msg = None
	if options.put is not None:
		if not os.path.isfile(options.put): return (None, 'File does not exist.')
		ftp_cmds = 'lcd %s; mkdir -p %s; cd %s; put %s' % (local_path, remote_path, remote_path, filename)
		success_msg = "Uploaded '%s' to %s." % (filename, config['host'])
	elif options.fetch is not None:
		ftp_cmds = 'lcd %s; cd %s; get %s' % (local_path, remote_path, filename)
		success_msg = "Fetched '%s' from %s." % (filename, config['host'])
	elif options.mirror is not None:
		ftp_cmds = 'mirror -R %s %s' % (local_path, remote_path)
		success_msg = "Mirrored '%s' from %s." % (local_path, config['host'])
	
	ftp_cmds="set net:max-retries 1; set cmd:trace true; %s" % ftp_cmds
	cmd = 'lftp -c "o %s; user %s %s; %s"' % (getHostUri(config), config['user'], config['pass'], ftp_cmds)

	#if DEBUG: print cmd
	
	return (cmd, success_msg)

def getFilename(options):
	if options.put is not None: return os.path.realpath(options.put)
	if options.fetch is not None: return os.path.realpath(options.fetch)
	if options.mirror is not None: return os.path.realpath(options.mirror)
	
	return None
	
def getHostUri(config):
	host=config['host']
	protocol='ftp'
	if 'protocol' in config:
		protocol=config['protocol']

	return protocol+"://"+host

def growl(title, message):	
	subprocess.call('growlnotify -n lftp.bundle -t "%s" -m "%s"' % (title, message), shell=True)

(success, message) = run()
# if success:
# 	growl('Success', message)
# else:
#if not success:
#	growl('Failure', message)