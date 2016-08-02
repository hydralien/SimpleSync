#
# Sublime Text SimpleSync plugin
#
# Help the orphans, street children, disadvantaged people
#   and physically handicapped in Vietnam (http://bit.ly/LPgJ1m)
#
# @copyright (c) 2012 Tan Nhu, tnhu AT me . COM
# @version 0.0.1
# @licence MIT
# @link https://github.com/tnhu/SimpleSync
#
from __future__ import print_function, unicode_literals
import sublime
import sublime_plugin
import subprocess
import threading
import tempfile

#
# Run a process
# @param cmd process command
#
def runProcess(cmd):
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  
  retcode = None
  while (True):
    retcode = p.poll()             #returns None while subprocess is running
    line    = p.stdout.readline()
    print(line.decode('utf-8'), end='')

    if (retcode is not None):
      break

  if not retcode: # result is OK if return value is 0, we're reversing it here for readbility
    return True
  return False

#
# Get sync item(s) for a file
# @param local_file full path of a local file
# @return sync item(s)
#
def getSyncItem(local_file):
  # Populate settings
  settings = sublime.load_settings("SimpleSync.sublime-settings")
  sync     = settings.get("sync")

  ret = []

  for item in sync:
    if local_file.startswith(item["local"]):
      ret += [item]

  return ret

#
# ScpCopier does actual copying using threading to avoid UI blocking
#
class ScpCopier(threading.Thread):
  def __init__(self, host, username, local_file, remote_file, port=22):
    self.host        = host
    self.port        = port
    self.username    = username
    self.local_file  = local_file
    self.remote_file = remote_file

    threading.Thread.__init__(self)

  def run(self):
    remote  = self.username + "@" + self.host + ":" + self.remote_file

    print("SimpleSync: ", self.local_file, " -> ", remote)

    if not runProcess(["scp", "-r", "-P", str(self.port) , self.local_file, remote]):
      sublime.status_message("Copying to {} on {} failed, see console for details".format(self.remote_file, self.host))
    else:
      sublime.status_message("Saved {} on {}!".format(self.remote_file, self.host))
      

class FromScpCopier():
  def __init__(self, host, username, local_file, remote_file, port=22):
    self.host        = host
    self.port        = port
    self.username    = username
    self.local_file  = local_file
    self.remote_file = remote_file

  def start(self):
    remote  = self.username + "@" + self.host + ":" + self.remote_file
    temp_file = tempfile.NamedTemporaryFile()

    print("SimpleSync: ", remote, " -> ", self.local_file, " via temp file ", temp_file.name)

    if not runProcess(["scp", "-r", "-P", str(self.port), remote, temp_file.name]):
      sublime.status_message("Reading {} on {} failed (but maybe it just does not exist yet), see console for details".format(self.remote_file, self.host))
      return

    print("Compare ", temp_file.name, " to ", self.local_file)

    no_diff = runProcess(["cmp", temp_file.name, self.local_file])

    if not no_diff:
      if (sublime.ok_cancel_dialog("Local file is different from remote! Replace local file?", "Yes please")):
        if not runProcess(['cp', temp_file.name, self.local_file]):
          sublime.status_message("Cannot update local file, check console for details")
        else:
          sublime.status_message("Local file updated")

    temp_file.close()

#
# LocalCopier does local copying using threading to avoid UI blocking
#
class LocalCopier(threading.Thread):
  def __init__(self, local_file, remote_file):
    self.local_file  = local_file
    self.remote_file = remote_file
    threading.Thread.__init__(self)

  def run(self):
    print("SimpleSync: ", self.local_file, " -> ", self.remote_file)

    if not runProcess(['cp', self.local_file, self.remote_file]):
      sublime.status_message("Cannot copy file locally, check console for details")
    else:
      sublime.status_message("File saved to local mirror")

#
# Subclass sublime_plugin.EventListener
#
class SimpleSync(sublime_plugin.EventListener):
  def on_load(self, view):
    settings     = sublime.load_settings("SimpleSync.sublime-settings")
    sync_on_open = settings.get("sync_on_open", True)
    if not sync_on_open:
      return

    local_file = view.file_name()
    syncItems  = getSyncItem(local_file)

    if (len(syncItems) > 0):
      for item in syncItems:
        remote_file = local_file.replace(item["local"], item["remote"])

        if (item["type"] == "ssh"):
          FromScpCopier(item["host"], item["username"], local_file, remote_file, port=item["port"]).start()


  def on_post_save(self, view):
    local_file = view.file_name()
    syncItems  = getSyncItem(local_file)

    if (len(syncItems) > 0):
      for item in syncItems:
        remote_file = local_file.replace(item["local"], item["remote"])

        if (item["type"] == "ssh"):
          ScpCopier(item["host"], item["username"], local_file, remote_file, port=item["port"]).start()
        elif (item["type"] == "local"):
          LocalCopier(local_file, remote_file).start()
