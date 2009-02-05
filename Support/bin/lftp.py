#!/usr/local/bin/python2.6
# TODO: handle multiple file put,fetch
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
	parser.add_option("-c", "--config", dest="config_dir", help="path to config dir")
	parser.set_defaults(config_dir="config")

	(options, args) = parser.parse_args()
	
	parser.check_required(["-f", "-p", "-m"])

	#if not os.path.isfile(options.filename): return (False, 'File does not exist.')

	#files=glob.glob('config/*.json')
	files=glob.glob(options.config_dir+'/*.json')

	readone=False
	msg=""
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
			continue
	
		local_path=os.path.realpath(config['local_path'])
		relpath=os.path.relpath(getFilename(options), local_path)
		
		if DEBUG:
			print "Loaded %s...<br />" % (f)
			print getFilename(options)+"<br />"
			print local_path+"<br />"
			print "relpath=%s<br />" % relpath
			#print config
		
		
		if relpath.find("..") == -1:
			#we have a match
			readone=True
			
			(cmd, success_msg) = getFtpCommand(options, config)
			if cmd is None: #error
				return (False, success_msg)
			
			#todo: get output as error
			success=subprocess.call(cmd, shell=True)
			if success==0: 
				msg+=success_msg+"\n"
			else:
				msg+="fail?\n"
				
		if DEBUG: print "<hr />"
		
	if not readone:
		msg="No sites found for the current file."
	
	return (readone, msg)

def getFtpCommand(options, config):	
	#if DEBUG: print "Uploading '%s' to %s..." % (relpath, config['host'])
	
	fname = getFilename(options)
	local_path=os.path.realpath(config['local_path'])
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
		ftp_cmds = 'lcd %s; mkdir -p %s; cd %s; put %s' % (config['local_path'], remote_path, remote_path, relpath)
		success_msg = "Uploaded '%s' to %s." % (filename, config['host'])
	elif options.fetch is not None:
		ftp_cmds = 'lcd %s; cd %s; get %s' % (local_path, remote_path, relpath)
		success_msg = "Fetched '%s' from %s." % (filename, config['host'])
	elif options.mirror is not None:
		ftp_cmds = 'mirror -R %s %s' % (local_path, remote_path)
		success_msg = "Mirrored '%s' from %s." % (local_path, config['host'])
		
	cmd = 'lftp -c "o %s; user %s %s; %s"' % (getHostUri(config), config['user'], config['pass'], ftp_cmds)

	if DEBUG: print cmd
	
	return (cmd, success_msg)

def getFilename(options):
	if options.put is not None: return options.put
	if options.fetch is not None: return options.fetch
	if options.mirror is not None: return options.mirror
	
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
if success:
	growl('Success', message)
else:
	growl('Failure', message)