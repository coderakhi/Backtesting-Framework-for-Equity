try:
    from .connect import KiteConnectProxy
    from .exceptions import *
    from .ticker import KiteTicker
except ModuleNotFoundError:
    import subprocess
    import sys

    install_requires = [
        "service_identity>=18.1.0",
        "requests>=2.18.4",
        "six>=1.11.0",
        "pyOpenSSL>=17.5.0",
        "enum34>=1.1.6",
        "python-dateutil>=2.6.1",
        "autobahn[twisted]==19.11.2"
    ]

    for package in install_requires:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

    from .connect import KiteConnectProxy
    from .exceptions import *
    from .ticker import KiteTicker