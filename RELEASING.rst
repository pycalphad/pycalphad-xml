Releasing pycalphad-xml
=======================

Create a release of pycalphad-xml
---------------------------------
To release a new version of pycalphad-xml:

These steps assume that ``0.1`` is the most recently tagged version number and ``0.2`` is the next version number to be released.
Replace their values with the last public release's version number and the new version number as appropriate.

#. Determine what the next version number should be using `semantic versioning <https://semver.org/>`_.
#. Resolve or defer all pull requests and issues tagged with the upcoming version milestone.
#. ``git stash`` to save any uncommitted work.
#. ``git checkout main``
#. ``git pull`` to make sure you haven't missed any last-minute commits. **After this point, nothing else is making it into this version.**
#. ``pytest`` to ensure that all tests pass locally.
#. Update ``CHANGES.rst`` with a human-readable list of changes since the last commit.
   ``git log --oneline --no-decorate --color 0.1^..main`` can be used to list the changes since the last version.
#. ``git add CHANGES.rst`` to stage the updated documentation.
#. ``git commit -m "REL: 0.2"`` to commit the changes.
#. ``git push origin main``
#. **Verify that all continuous integration test and build workflows pass.**
#. Create a release on GitHub

   #. Go to https://github.com/pycalphad/pycalphad-xml/releases/new
   #. Set the "Tag version" field to ``0.2``.
   #. Set the branch target to ``main``.
   #. Set the "Release title" to ``pycalphad-xml 0.2``.
   #. Leave the description box blank.
   #. If this version is a pre-release, check the "This is a pre-release" box.
   #. Click "Publish release".
#. The new version will be available on PyPI when the ``Build and deploy to PyPI`` workflow on GitHub Actions finishes successfully.

Deploy to PyPI (manually)
-------------------------

.. warning::

   DO NOT FOLLOW THESE STEPS unless the GitHub Actions deployment workflow is broken.
   Creating a GitHub release should trigger the ``Build and deploy to PyPI`` workflow on GitHub Actions that will upload source and platform-dependent wheel distributions automatically.

To release a source distribution to PyPI:

#. If deploying for the first time: ``pip install twine build``
#. ``rm -R dist/*`` on Linux/OSX or ``del dist/*`` on Windows
#. ``git checkout main`` to checkout the latest version
#. ``git pull``
#. ``git log`` to verify the repository state matches the newly created tag

#. ``python -m build --sdist``
#. **Make sure that the script correctly detected the new version exactly and not a dirty / revised state of the repo.**
#. ``twine upload dist/*`` to upload (assumes a `correctly configured <https://packaging.python.org/specifications/pypirc/>`_ ``~/.pypirc`` file)
