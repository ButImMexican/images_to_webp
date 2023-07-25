# -*- coding: utf-8 -*-
import odoo
from odoo import http, tools, _
from odoo.tools import image_process, file_open
from odoo.http import request
from odoo.addons.web.controllers.main import Binary
from odoo.addons.web_editor.controllers.main import Web_Editor
from odoo.exceptions import UserError
import base64, io, webp
from PIL import Image, ImageSequence
from ..models.ir_ui_view import check_webp_support


class Binary(Binary):
    def _content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'datas',
                       filename_field = 'name', unique = None, filename = None, mimetype = None,
                       download = None, width = 0, height = 0, crop = False, quality = 0, access_token = None,
                       placeholder = 'placeholder.png', **kwargs):
        webp_support = check_webp_support(request)
        convert_back_to_png = False
        w = width
        h = height

        if model and model == 'ir.attachment' and id:
            attachment = request.env[model].sudo().search([('id', '=', id)])

            if attachment and attachment.mimetype == "image/webp":
                quality = 0
                width = 0
                height = 0
                crop = False

                if not webp_support:
                    convert_back_to_png = True

        response = super(Binary, self)._content_image(xmlid = xmlid, model = model, id = id, field = field,
                                                      filename_field = filename_field, unique = unique,
                                                      filename = filename,
                                                      mimetype = mimetype,
                                                      download = download, width = width, height = height, crop = crop,
                                                      quality = quality, access_token = access_token)

        if convert_back_to_png and response.data:
            img_data = response.data
            webp_data = webp.WebPData.from_buffer(img_data)
            arr = webp_data.decode()
            source_image = Image.fromarray(arr, 'RGBA')

            if w or h:
                source_image.thumbnail((w, h))

            convert_to_png = io.BytesIO()
            source_image.save(convert_to_png, 'PNG')
            response.data = convert_to_png.getvalue()

        return response

    def _placeholder(self, image = False):
        if not image:
            image = 'web/static/img/placeholder.png'
        with file_open(image, 'rb', filter_ext = ('.png', '.jpg')) as fd:
            return fd.read()


class WebP(http.Controller):
    def _convert_image_to_webp(self, img_data, quality, webp_arr = False, format = None):
        source_image = webp_arr and img_data or Image.open(io.BytesIO(img_data))
        format = format or source_image.format

        if format == "GIF":
            fps = 10

            if webp_arr:
                pics = source_image
            else:
                pics = []

                for frame in ImageSequence.Iterator(source_image):
                    pics.append(webp.WebPPicture.from_pil(frame.copy()))

            enc_opts = webp.WebPAnimEncoderOptions.new()
            enc = webp.WebPAnimEncoder.new(pics[0].ptr.width, pics[0].ptr.height, enc_opts)
            config = webp.WebPConfig.new(lossless = True, quality = quality)

            for i, pic in enumerate(pics):
                t = round((i * 1000) / fps)
                enc.encode_frame(pic, t, config)

            end_t = round((len(pics) * 1000) / fps)
            anim_data = enc.assemble(end_t)

            return io.BytesIO(anim_data.buffer()).getvalue()
        else:
            pic = webp.WebPPicture.from_pil(source_image.convert("RGBA"))
            config = webp.WebPConfig.new(preset = webp.WebPPreset.PHOTO, quality = quality)

            return pic.encode(config).buffer()

    def _webp_to_buffer(self, img_data, quality, width, height, return_non_webp = False):
        webp_data = webp.WebPData.from_buffer(img_data)

        arrs = []
        pilmode = 'RGBA'
        fps = None

        if pilmode == 'RGBA':
            color_mode = webp.WebPColorMode.RGBA
        elif pilmode == 'RGBa':
            color_mode = webp.WebPColorMode.rgbA
        elif pilmode == 'RGB':
            color_mode = webp.WebPColorMode.RGBA
        else:
            raise webp.WebPError('unsupported color mode: ' + pilmode)

        dec_opts = webp.WebPAnimDecoderOptions.new(use_threads = True, color_mode = color_mode)
        dec = webp.WebPAnimDecoder.new(webp_data, dec_opts)
        eps = 1e-7

        for arr, frame_end_time in dec.frames():
            if pilmode == 'RGB':
                arr = arr[:, :, 0:3]
            if fps is None:
                arrs.append(arr)
            else:
                while len(arrs) * (1000 / fps) + eps < frame_end_time:
                    arrs.append(arr)

        if len(arrs) > 1:
            source_images = [Image.fromarray(arr, pilmode).convert(mode = 'RGBA') for arr in arrs]

            if width or height:
                for s_img in source_images:
                    s_img.thumbnail((width, height))

            if return_non_webp:
                convert_to_gif = io.BytesIO()
                source_images[0].save(convert_to_gif, "PNG", save_all = True, append_images = source_images[1:],
                                      loop = 0)
                img_data = convert_to_gif.getvalue()
            else:
                pics = [webp.WebPPicture.from_pil(img) for img in source_images]
                img_data = self._convert_image_to_webp(pics, quality, webp_arr = True, format = "GIF")
        else:
            arr = webp_data.decode()
            source_image = Image.fromarray(arr, 'RGBA')

            if width or height:
                source_image.thumbnail((width, height))

            if return_non_webp:
                convert_to_png = io.BytesIO()
                source_image.save(convert_to_png, 'PNG')
                img_data = convert_to_png.getvalue()
            else:
                pic = webp.WebPPicture.from_pil(source_image)
                config = webp.WebPConfig.new(preset = webp.WebPPreset.PHOTO, quality = quality)

                img_data = pic.encode(config).buffer()

        return return_non_webp and img_data or base64.b64encode(img_data)

    @http.route([
            '/webp/image',
            '/webp/image/<string:xmlid>',
            '/webp/image/<string:xmlid>/<string:filename>',
            '/webp/image/<string:xmlid>/<int:width>x<int:height>',
            '/webp/image/<string:xmlid>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<string:model>/<int:id>/<string:field>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<string:filename>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>',
            '/webp/image/<string:model>/<int:id>/<string:field>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<int:id>',
            '/webp/image/<int:id>/<string:filename>',
            '/webp/image/<int:id>/<int:width>x<int:height>',
            '/webp/image/<int:id>/<int:width>x<int:height>/<string:filename>',
            '/webp/image/<int:id>-<string:unique>',
            '/webp/image/<int:id>-<string:unique>/<string:filename>',
            '/webp/image/<int:id>-<string:unique>/<int:width>x<int:height>',
            '/webp/image/<int:id>-<string:unique>/<int:width>x<int:height>/<string:filename>'
            ], type = 'http', auth = "public")
    def content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'datas',
                      filename_field = 'name', unique = None, filename = None, mimetype = None,
                      download = None, width = 0, height = 0, crop = False, access_token = None,
                      **kwargs):
        return self._content_image(xmlid = xmlid, model = model, id = id, field = field,
                                   filename_field = filename_field, unique = unique, filename = filename,
                                   mimetype = mimetype,
                                   download = download, width = width, height = height, crop = crop,
                                   quality = int(kwargs.get('quality', 0)), access_token = access_token)

    def _content_image(self, xmlid = None, model = 'ir.attachment', id = None, field = 'datas',
                       filename_field = 'name', unique = None, filename = None, mimetype = None,
                       download = None, width = 0, height = 0, crop = False, quality = 0, access_token = None,
                       placeholder = 'placeholder.png', **kwargs):
        webp_support = check_webp_support(request)
        is_webp = False

        if model and model == 'ir.attachment' and id:
            attachment = request.env[model].sudo().search([('id', '=', id)])
        else:
            attachment = request.env['ir.attachment'].sudo().search([('res_model', '=', model),
                                                                     ('res_id', '=', id),
                                                                     ('res_field', '=', field)], limit = 1)

        if attachment and attachment.mimetype == "image/webp":
            is_webp = True

        status, headers, image_base64 = request.env['ir.http'].binary_content(
                xmlid = xmlid, model = model, id = id, field = field, unique = unique, filename = filename,
                filename_field = filename_field, download = download, mimetype = mimetype,
                default_mimetype = 'image/png', access_token = access_token)

        if status in [301, 304] or (status != 200 and download):
            return request.env['ir.http']._response_by_status(status, headers, image_base64)
        if not image_base64:
            status = 200
            placeholder_filename = False

            if model in request.env:
                placeholder_filename = request.env[model]._get_placeholder_filename(field)

            image_base64 = base64.b64encode(Binary()._placeholder(image = placeholder_filename))
            if not (width or height):
                width, height = odoo.tools.image_guess_size_from_field_name(field)

        if headers and dict(headers).get('Content-Type', '') != 'image/svg+xml':
            try:
                Image.open(io.BytesIO(base64.b64decode(image_base64)))
            except Exception:
                is_webp = True

        if not is_webp:
            image_base64 = image_process(image_base64, size = (int(width), int(height)), crop = crop,
                                         quality = quality)
        else:
            if webp_support:
                width = int(width or height) or 0
                height = int(height or width) or 0
                quality = quality or int(request.session.get('webp_image_quality', 95)) or 95

                image_base64 = self._webp_to_buffer(base64.b64decode(image_base64), quality, width, height)

        img_data = base64.b64decode(image_base64)
        headers = http.set_safe_image_headers(headers, img_data)

        if headers and dict(headers).get('Content-Type', '') != 'image/svg+xml':
            width = width or height or 0
            height = height or width or 0

            if webp_support:
                quality = quality or int(request.session.get('webp_image_quality', 95)) or 95

                if not is_webp:
                    img_data = self._convert_image_to_webp(img_data, quality)
            else:
                if is_webp:
                    img_data = self._webp_to_buffer(img_data, quality, width, height, return_non_webp = True)

            for key, item in enumerate(headers):
                if item[0] == 'Content-Type':
                    headers[key] = ('Content-Type', webp_support and 'image/webp' or 'image/png')
                if item[0] == 'Content-Length':
                    headers[key] = ('Content-Length', len(img_data))

        response = request.make_response(img_data, headers)
        response.status_code = status
        return response


class Web_Editor(Web_Editor):
    def _attachment_create(self, name = '', data = False, url = False, res_id = False, res_model = 'ir.ui.view',
                           generate_access_token = False,
                           is_webp = False):
        """Create and return a new attachment."""
        if name.lower().endswith('.bmp'):
            # Avoid mismatch between content type and mimetype, see commit msg
            name = name[:-4]

        if not name and url:
            name = url.split("/").pop()

        if res_model != 'ir.ui.view' and res_id:
            res_id = int(res_id)
        else:
            res_id = False

        attachment_data = {
                'name': name,
                'public': res_model == 'ir.ui.view',
                'res_id': res_id,
                'res_model': res_model,
                }

        if data:
            attachment_data[is_webp and 'raw' or 'datas'] = data
        elif url:
            attachment_data.update({
                    'type': 'url',
                    'url': url,
                    })
        else:
            raise UserError(_("You need to specify either data or url to create an attachment."))

        attachment = request.env['ir.attachment'].create(attachment_data)

        if generate_access_token:
            attachment.generate_access_token()

        return attachment

    @http.route('/web_editor/attachment/add_data', type = 'json', auth = 'user', methods = ['POST'], website = True)
    def add_data(self, name, data, is_image, quality = 0, width = 0, height = 0, res_id = False,
                 res_model = 'ir.ui.view', generate_access_token = False, **kwargs):
        website = request.website
        webp_config = website and website.enable_webp_compress or False

        if webp_config:
            is_webp = False

            try:
                data = base64.b64decode(data)
                data = WebP._convert_image_to_webp(self, data, quality = quality or website.webp_image_quality or 95)
                data = base64.b64encode(data)
            except Exception:
                is_webp = True

            attachment = self._attachment_create(name = name, data = data, res_id = res_id, res_model = res_model,
                                                 generate_access_token = generate_access_token,
                                                 is_webp = is_webp)
            result = attachment._get_media_info()

            name = name.split('.')[0]
            name += ".webp"
            attachment.name = name
            attachment.mimetype = "image/webp"

            return result
        else:
            return super(Web_Editor, self).add_data(name = name, data = data,
                                                    is_image = is_image,
                                                    quality = quality,
                                                    width = width,
                                                    height = height,
                                                    res_id = res_id,
                                                    res_model = res_model,
                                                    generate_access_token = generate_access_token,
                                                                            **kwargs)
