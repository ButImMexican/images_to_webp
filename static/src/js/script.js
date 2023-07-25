odoo.define('images_to_webp.media', function (require) {
    var FileWidgetClass = require('wysiwyg.widgets.media');

    FileWidgetClass.FileWidget.include({
        IMAGE_MIMETYPES: ['image/gif', 'image/jpe', 'image/jpeg', 'image/jpg', 'image/gif', 'image/png', 'image/svg+xml', 'image/webp'],
        IMAGE_EXTENSIONS: ['.jpg', '.jpeg', '.jpe', '.png', '.svg', '.gif', '.webp'],
    });

    return FileWidgetClass;
});

odoo.define('images_to_webp.editor', function (require) {
    var EditorMenuBar = require('web_editor.snippet.editor');

    EditorMenuBar.SnippetsMenu.include({
        init: function (parent, options) {
            var self = this;
            var res = self._super.apply(self, arguments);

            $('body picture').each(function (_, elem) {
                $(elem).replaceWith($(elem).find('img'));
            });

            return res;
        }
    });

    return EditorMenuBar;
});

odoo.define('images_to_webp.website_sale_cart', function (require) {
    require('website_sale.cart');

    var publicWidget = require('web.public.widget');
    var timeout;

    publicWidget.registry.websiteSaleCartLink.include({
        _onMouseEnter: function (ev) {
            var self = this;
            clearTimeout(timeout);
            $(this.selector).not(ev.currentTarget).popover('hide');
            timeout = setTimeout(function () {
                if (!self.$el.is(':hover') || $('.mycart-popover:visible').length) {
                    return;
                }
                self._popoverRPC = $.get("/shop/cart", {
                    type: 'popover',
                }).then(function (data) {
                    self.$el.data("bs.popover").config.content = $(data);
                    self.$el.popover("show");
                    $('.popover').on('mouseleave', function () {
                        self.$el.trigger('mouseleave');
                    });
                });
            }, 300);
        },
    })
});