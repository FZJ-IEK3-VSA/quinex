from manage_analyses_api import CONFIG, PAPER_ANALYSIS_SERVICES_DIR


log_path = PAPER_ANALYSIS_SERVICES_DIR / CONFIG["manage_analyses_api"]["log_path"]

LOGGING_CONFIG = { 
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': { 
        'standard': { 
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'custom_formatter': { 
            'format': "%(asctime)s [%(processName)s: %(process)d] [%(threadName)s: %(thread)d] [%(levelname)s] %(name)s: %(message)s"
            
        },
    },
    'handlers': { 
        'default': { 
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'stream_handler': { 
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'file_handler': { 
            'formatter': 'custom_formatter',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_path,
            'maxBytes': 1024 * 1024 * 1,
            'backupCount': 3,
        },
    },
    'loggers': { 
        'uvicorn': {
            'handlers': ['default', 'file_handler'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn.access': {
            'handlers': ['stream_handler', 'file_handler'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn.error': { 
            'handlers': ['stream_handler', 'file_handler'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn.asgi': {
            'handlers': ['stream_handler', 'file_handler'],
            'level': 'INFO',
            'propagate': False
        },

    },
}