from setuptools import setup
from py2exe2msi.command import py2exe2msi
import msilib

# http://msdn.microsoft.com/en-us/library/windows/desktop/aa371847(v=vs.85).aspx
class py2exe2msi_with_shortcuts(py2exe2msi):
    def initialize_options(self):
        self.shortcuts = []
        py2exe2msi.initialize_options(self)

    def run(self):
        py2exe2msi.run(self)
        msilib.schema.Shortcut.create(self.db)
        if self.shortcuts:
            msilib.add_data(self.db, 'Shortcut', self.shortcuts)
            self.db.Commit()

setup(
    cmdclass     = { 'py2exe2msi' : py2exe2msi_with_shortcuts },
    name         = 'Big Clock',
    version      = '1.2',
    description  = 'A big clock for race control',
    author       = 'Jeffrey Hutzelman',
    author_email = 'jhutz@cmu.edu',
    windows      = ['big-clock'],
    data_files   = [('',['big-clock.html','big-clock.css','big-clock.js'])],
    options      = {
        'py2exe': {
        },
        'py2exe2msi': {
            'pfiles_dir':   'Big Clock',
            'upgrade_code': '7cdf937a-3b03-433e-84c1-27f26f7c801f',
            'shortcuts': [
                ('ProgramMenuShortcut',      # Shortcut
                 'ProgramMenuFolder',        # Directory_
                 'Big Clock',                # Name
                 'BIG_CLOCK.EXE',            # Component_
                 '[#big_clock.exe]',         # Target
                 None,                       # Arguments
                 None,                       # Description
                 None,                       # Hotkey
                 None,                       # Icon
                 None,                       # IconIndex
                 None,                       # ShowCmd
                 None,                       # WkDir
                 )
            ],
        },
    },
)
