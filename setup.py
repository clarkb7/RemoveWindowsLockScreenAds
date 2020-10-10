from setuptools import setup

with open("README.md", "r") as f:
    long_desc = f.read()

setup(
    name='RemoveWindowsLockScreenAds',
    version='0.1',
    description='Remove Windows lock screen ads/Spotlight ads while keeping the rotating Spotlight image backgrounds.',
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url='https://github.com/clarkb7/RemoveWindowsLockScreenAds',
    license='MIT',

    author='Branden Clark',
    author_email='clark@rpis.ec',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Utilities',
    ],
    keywords='windows-spotlight remove-ads windows-lockscreen',

    packages=['RemoveWindowsLockScreenAds'],
    install_requires=['pywin32'],
)

