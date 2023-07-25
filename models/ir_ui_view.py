# -*- coding: utf-8 -*-

import copy
import os
import base64
import re

from lxml.etree import tostring as htmlstring
from lxml.html import fromstring, Element
from odoo import models, api, tools
from odoo.http import request
import importlib, webp
from PIL import Image, ImageSequence
from werkzeug.urls import url_quote

SUPPORTED_IMAGE_MIMETYPES = ['image/gif', 'image/jpe', 'image/jpeg', 'image/jpg', 'image/png', 'image/svg+xml',
                             'image/webp']
SUPPORTED_IMAGE_EXTENSIONS = ['.gif', '.jpe', '.jpeg', '.jpg', '.png', '.svg', '.webp']


def check_webp_support(request):
    return request.httprequest.accept_mimetypes.accept_json or (
            'image/webp' in request.httprequest.headers.get('Accept', ''))


def generate_web_image(url, quality):
    split_url = url.lstrip('/').split('/')
    module_name = split_url[0]
    module = importlib.import_module("odoo.addons.%s" % module_name)
    image_name = split_url[-1].split('.')

    if image_name[1] == 'svg':
        return url

    image_name = image_name[0] + ".webp"
    del split_url[0]

    current_dir = os.path.dirname(module.__file__)
    original_path = current_dir + "/" + '/'.join(split_url)
    split_url[-1] = image_name
    webp_url = "/" + '/'.join(split_url)
    webp_path = current_dir + webp_url
    webp_url = "/" + module_name + webp_url

    if os.path.exists(webp_path):
        return webp_url
    elif os.path.exists(original_path):
        try:
            original_image = Image.open(original_path)
            pics = []

            for frame in ImageSequence.Iterator(original_image):
                pics.append(frame.copy())

            webp.save_images(pics, webp_path, quality = quality, fps=10, lossless=True)
        except:
            return url

        return webp_url

    return url


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _render_template(self, template, values = None, engine = 'ir.qweb'):
        res = super(IrUiView, self)._render_template(template, values, engine)
        has_doctype = re.search(r"<!doctype\s+html>", res[:15], re.IGNORECASE)

        try:
            website = request.website
        except:
            website = False

        webp_config = website and website.enable_webp_compress or False

        if check_webp_support(request) and values and webp_config:
            request.session['webp_image_quality'] = website.webp_image_quality or 95

            try:
                res = res.decode("utf-8", "ignore").encode("ascii", "xmlcharrefreplace")
            except:
                pass

            res = fromstring(res)
            images = res.cssselect('img:not([src*="base64"])')

            for img in images:
                picture_tag = Element('picture')
                source_tag = Element('source')
                source_tag.attrib['type'] = "image/webp"
                source_tag.attrib['srcset'] = '/static/' in img.attrib['src'] and generate_web_image(
                        img.attrib['src'], request.session['webp_image_quality']) or img.attrib['src'].replace(
                        '/web/image', '/webp/image')
                picture_tag.insert(0, copy.copy(img))
                picture_tag.insert(0, source_tag)
                img.getparent().replace(img, picture_tag)

            res = htmlstring(res, method = "html",
                             doctype = '<!DOCTYPE html>' if has_doctype else None)
            res = re.sub(r"(<img[^>]+)>", "\\1/>", res.decode("utf-8"), 0, re.MULTILINE)

            if request.httprequest.accept_mimetypes.accept_json:
                if res.startswith('<div>') and res.endswith('</div>'):
                    res = res[5:-6]

            res = bytes(res.encode("utf-8")).decode("utf-8")

        return res


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.depends('mimetype', 'url', 'name')
    def _compute_image_src(self):
        for attachment in self:
            # Only add a src for supported images
            if attachment.mimetype not in SUPPORTED_IMAGE_MIMETYPES:
                attachment.image_src = False
                continue

            if attachment.type == 'url':
                attachment.image_src = attachment.url
            else:
                # Adding unique in URLs for cache-control
                unique = attachment.checksum[:8]
                if attachment.url:
                    # For attachments-by-url, unique is used as a cachebuster. They
                    # currently do not leverage max-age headers.
                    separator = '&' if '?' in attachment.url else '?'
                    attachment.image_src = '%s%sunique=%s' % (attachment.url, separator, unique)
                else:
                    name = url_quote(attachment.name)
                    attachment.image_src = '/web%s/image/%s-%s/%s' % (attachment.mimetype == 'image/webp' and 'p' or '', attachment.id, unique, name)

    @api.depends('datas')
    def _compute_image_size(self):
        for attachment in self:
            try:
                if attachment.mimetype == "image/webp":
                    data_image = base64.b64decode(attachment.datas)
                    webp_data = webp.WebPData.from_buffer(data_image)
                    arr = webp_data.decode()
                    source_image = Image.fromarray(arr, 'RGBA')

                    attachment.image_width = source_image.width
                    attachment.image_height = source_image.height
                else:
                    image = tools.base64_to_image(attachment.datas)
                    attachment.image_width = image.width
                    attachment.image_height = image.height
            except Exception:
                attachment.image_width = 0
                attachment.image_height = 0
