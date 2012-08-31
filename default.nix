with import <nixpkgs> {};

pythonPackages.buildPythonPackage rec {
  name = "lastwatch-0.3.1";
  namePrefix = "";

  src = ./.;

  pythonPath = [
    pythonPackages.pyinotify
    pythonPackages.pylast
    pythonPackages.mutagen
  ];

  propagatedBuildInputs = pythonPath;

  installCommand = "python setup.py install --prefix=$out";
}
