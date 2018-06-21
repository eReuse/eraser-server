from setuptools import setup, find_packages

setup(
    name='EraserManager',
    version='0.1',
    packages=find_packages(exclude=('contrib', 'docs', 'scripts')),
    url='https://github.com/eReuse/eraser-server',
    license='AGPLv3 License',
    author='eReuse.org team',
    author_email='adrias@ereuse.org',
    description='Massively and securely erase hard-drives.',
    # Updated in 2018--29
    install_requires=[
        'ereuse-workbench'
    ],
    dependency_links=[
        'git+https://github.com/ereuse/workbench#egg=ereuse-workbench-8.0.0beta1'
    ],
    keywords='eReuse.org EraserManager Massively securely erase storage devices hard-drives',
    # http://setuptools.readthedocs.io/en/latest/setuptools.html#test-build-package-and-run-a-unittest-suite
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Manufacturing',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Natural Language :: English',
        'Operating System :: Debian',
        'Programming Language :: Python :: 2.7',
        'Topic :: Office/Business',
    ]
)
