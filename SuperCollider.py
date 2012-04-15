import sublime, sublime_plugin
import sys
import subprocess
import threading
import os
import webbrowser

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

# command to start SuperCollider interpreter sclang
class Sc_startCommand(sublime_plugin.WindowCommand):
    sclang_process = None
    sclang_queue = None
    sclang_thread = None
    output_view = None
    panel_name = None

    def run(self):
        # create output panel
        if Sc_startCommand.output_view is None:
            print "Creating output view for SuperCollider"
            Sc_startCommand.panel_name = "supercollider"
            Sc_startCommand.output_view = self.window.get_output_panel(Sc_startCommand.panel_name)

        # start supercollider
        if Sc_startCommand.sclang_thread is None or not Sc_startCommand.sclang_thread.isAlive():
            settings = sublime.load_settings("SuperCollider.sublime-settings")
            sc_dir = settings.get("sc_dir")
            sc_exe = settings.get("sc_exe")
            print "Starting SuperCollider : "+sc_dir+sc_exe
            Sc_startCommand.sclang_process = subprocess.Popen([sc_exe, '-i', 'sublime'], cwd=sc_dir, bufsize=1, close_fds=ON_POSIX, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines=True, shell=True)
            Sc_startCommand.sclang_queue = Queue()
            Sc_startCommand.sclang_thread = threading.Thread(target=enqueue_output, args=(Sc_startCommand.sclang_process.stdout, Sc_startCommand.sclang_queue))
            Sc_startCommand.sclang_thread.daemon = True # thread dies with the program
            Sc_startCommand.sclang_thread.start()
            print "SuperCollider has started"

        sublime.set_timeout(self.scrolldown, 100)
        sublime.set_timeout(self.poll, 1000)

    def poll(self):
        # continue while sclang is running
        if Sc_startCommand.sclang_thread is not None and Sc_startCommand.sclang_thread.isAlive():
            scReturnedSomething = True;
            somethingHappened = False

            edit = Sc_startCommand.output_view.begin_edit()

            while scReturnedSomething:
                try:  line = Sc_startCommand.sclang_queue.get_nowait()
                except Empty:
                    scReturnedSomething = False
                else:
                    somethingHappened = True 
                    Sc_startCommand.output_view.insert(edit, Sc_startCommand.output_view.size(), line.decode("utf-8","ignore"))
           
            Sc_startCommand.output_view.end_edit(edit)

            if somethingHappened :
                sublime.set_timeout(self.scrolldown, 100)

            sublime.set_timeout(self.poll, 500)

    def scrolldown(self):
        if Sc_startCommand.output_view is not None:
            Sc_startCommand.output_view.show(Sc_startCommand.output_view.size()) # scroll down
            self.window.run_command("show_panel", {"panel": "output." + Sc_startCommand.panel_name})


# command to stop SuperCollider interpreter sclang
class Sc_stopCommand(sublime_plugin.WindowCommand):
    def run(self):
        print "Stopping supercollider"
        if Sc_startCommand.sclang_thread is not None and Sc_startCommand.sclang_thread.isAlive():
            Sc_startCommand.sclang_process.stdin.write("0.exit;\x0c")
            Sc_startCommand.sclang_process.stdin.flush()

# command to send the current line to sclang
class Sc_sendCommand(sublime_plugin.WindowCommand):
    def run(self):
        if Sc_startCommand.sclang_thread is not None and Sc_startCommand.sclang_thread.isAlive():
            view = self.window.active_view()
            sel = view.sel()
            point = sel[0]
            line = view.line(point)
            line_str = view.substr(line)
            # if the selection comprises of only character and it's a ( or ), expand
            if (point.a == point.b) and (line_str[0] == '(' or line_str[0] == ')'):
                view.run_command("expand_selection", {"to": "brackets"})
            sel = view.sel()
            region = view.line(sel[0])
            lines = view.substr(region).split("\n")
            for l in lines:
                Sc_startCommand.sclang_process.stdin.write(l.encode("utf-8","ignore")+"\n")
            Sc_startCommand.sclang_process.stdin.write("\x0c")
            Sc_startCommand.sclang_process.stdin.flush()

# command to show the supercollider console
class Sc_show_consoleCommand(sublime_plugin.WindowCommand):
    def run(self):
        if Sc_startCommand.output_view is not None:
            Sc_startCommand.output_view.show(Sc_startCommand.output_view.size()) # scroll down
            self.window.run_command("show_panel", {"panel": "output." + Sc_startCommand.panel_name})

# hide console
class Sc_hide_consoleCommand(sublime_plugin.WindowCommand):
    def run(self):
        if Sc_startCommand.output_view is not None:
            Sc_startCommand.output_view.show(Sc_startCommand.output_view.size()) # scroll down
            self.window.run_command("hide_panel", {"panel": "output." + Sc_startCommand.panel_name})

# stop all sounds
class Sc_stop_all_soundsCommand(sublime_plugin.WindowCommand):
    def run(self):
        if Sc_startCommand.sclang_thread is not None and Sc_startCommand.sclang_thread.isAlive():
            Sc_startCommand.sclang_process.stdin.write("thisProcess.stop;\x0c")
            Sc_startCommand.sclang_process.stdin.flush()

# search for help on current word on SCCode.org
class Sc_get_helpCommand(sublime_plugin.WindowCommand):
    sccode_search_url = None

    def run(self):
        if Sc_get_helpCommand.sccode_search_url is None:
            settings = sublime.load_settings("SuperCollider.sublime-settings")
            Sc_get_helpCommand.sccode_search_url = settings.get("sccode_search_url")
        view = self.window.active_view()
        sel = view.sel()
        point = sel[0]
        word = view.word(point)
        webbrowser.open_new_tab(Sc_get_helpCommand.sccode_search_url+view.substr(word))
