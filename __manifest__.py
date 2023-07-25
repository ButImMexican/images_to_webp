# -*- coding: utf-8 -*-
{
        "name": "WebP Image Optimizer",
        "summary": "WebP Image Optimizer",
        "description": """
		Install dependencies:
		`pip3 install webp`
		`pip3 install cssselect`
	""",
        "website": "erpswiss.com",
        'author': "Erpswiss",
        "category": "Website",
        "version": "15.0.2.3",
        "sequence": 1,
        'license': 'OPL-1',
        "depends": ['website'],
        "data": [
                'views/views.xml',
                ],
        'images': [
                'static/description/banner.png',
                'static/description/banner.jpg',
                ],
        "external_dependencies": {
                "python": [
                        "webp",
                        "cssselect",
                        "lxml"
                        ],
                },
        "assets": {
                'web.assets_frontend_lazy': [
                        "/images_to_webp/static/src/js/script.js"
                        ],
                },
        "application": True,
        'installable': True,
        'auto_install': False,
        "support": "support@erpswiss.com",
        "price": 50,
        "currency": "EUR",
        }
