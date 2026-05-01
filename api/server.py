<<<<<<< HEAD
"""
兼容层 - 旧版 API 入口
保留用于向后兼容
"""

from src.api.server import app
=======
﻿from src.api.server import app
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39


if __name__ == "__main__":
    import uvicorn

<<<<<<< HEAD
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
=======
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
