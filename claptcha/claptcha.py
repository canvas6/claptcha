# -*- coding: utf-8 -*-

import sys
import os
import random
from functools import wraps
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


class ClaptchaError(Exception):
    """Exception class for Claptcha errors"""
    pass


class Claptcha(object):
    def __init__(self, source, font, size=(200,80), margin=(20,20), **kwargs):
        r"""
        Claptcha object init.

        Claptcha object requires at least a text source (a string or a
        callable object returning a string) and a path to a TTF file. Both
        are used in generating text in returned CAPTCHA image with a given
        font. Callable object allow for creating variable CAPTCHAs without
        redeclaring Claptcha instance, e.g. a randomized stream of characters

        :param source:
            String or a callable object returning a string.
        :param font:
            Valid path (relative or absolute) to a TTF file.
        :param size:
            A pair with CAPTCHA size (width, height)
            in pixels.
        :param margin:
            A pair with CAPTCHA x and y margins in pixels
            Note that generated text may slightly overlap
            given margins, you should treat them only as
            an estimate.
        :param \**kwargs:
            See below

        :Keyword Arguments:
            * *format* (``string``) --
              Image format acceptable by Image class from PIL package.
            * *resample* (``int``) --
              Resampling filter. Allowed: Image.NEAREST, Image.BILINEAR and
              Image.BICUBIC. Default: Image.BILINEAR.
            * *noise* (``float``) --
              Parameter from range [0,1] used in creating noise effect in
              CAPTCHA image. If not larger than 1/255, no noise if generated. It is
              advised to not use this option if you want to focus on efficiency,
              since generating noise can significantly extend image creation time.
              Default: 0.
        """
        self.source = source
        self.size = size
        self.margin = margin
        self.font = font

        self.format = kwargs.get('format', 'PNG')
        self.resample = kwargs.get('resample', Image.BILINEAR)
        self.noise = abs(kwargs.get('noise', 0.))

    @property
    def image(self):
        r"""
        Tuple with a CAPTCHA text and an Image object.

        Images are generated on the fly, using given text source, TTF font and
        other parameters passable through __init__. All letters in used text are
        morphed. Also a line is morphed and pased onto CAPTCHA text. Additionaly,
        if self.noise > 1/255, a "snowy" image is merged with CAPTCHA image with
        a 50/50 ratio.
        Property returns a pair containing a string with text in returned image
        and image itself.

        :returns: ``tuple`` (CAPTCHA text, Image object)
        """
        text = self.text
        w, h = self.font.getsize(text)
        margin_x = round(self.margin_x * w / self.w)
        margin_y = round(self.margin_y * h / self.h)

        image = Image.new('RGB',
                          (w + 2*margin_x, h + 2*margin_y),
                          (255, 255, 255))

        # Text
        self._writeText(image, text, pos=(margin_x, margin_y))

        # Line
        self._drawLine(image)

        # White noise
        noise = self._whiteNoise(image.size)
        if noise is not None:
            image = Image.blend(image, noise, 0.5)

        return (text, image)

    @property
    def bytes(self):
        r"""
        Tuple with a CAPTCHA text and a BytesIO object.

        Property calls self.image and saves image contents in a BytesIO
        instance, returning CAPTCHA text and BytesIO as a tuple.
        See: image.

        :returns: ``tuple`` (CAPTCHA text, BytesIO object)
        """
        text, image = self.image
        bytes = BytesIO()
        image.save(bytes, format = self.format)
        bytes.seek(0)
        return (text, bytes)

    def write(self, file):
        text, image = self.image
        image.save(file, format = self.format)
        return (text, file)

    @property
    def source(self):
        return self.__source

    @source.setter
    def source(self, source):
        if not (isinstance(source, str) or callable(source)):
            raise ClaptchaError("source has to be either a string or be callable")
        self.__source = source

    @property
    def text(self):
        if isinstance(self.source, str):
            return self.source
        else:
            return self.source()

    def _with_pair_validator(func):
        @wraps(func)
        def wrapper(inst, pair):
            if not (hasattr(pair, '__len__') and hasattr(pair, '__getitem__')):
                raise ClaptchaError("Sequence not provided")
            if len(pair) != 2:
                raise ClaptchaError("Sequence has to have exactly 2 elements")
            return func(inst, pair)
        return wrapper

    @property
    def size(self):
        return self.__size
        
    @size.setter
    @_with_pair_validator
    def size(self, size):
        self.__size = (int(size[0]), int(size[1]))
       
    @property
    def w(self):
        return self.size[0]

    @property
    def h(self):
        return self.size[1]

    @property
    def margin(self):
        return self.__margin
    
    @margin.setter
    @_with_pair_validator
    def margin(self, margin):
        self.__margin = (int(margin[0]), int(margin[1]))

    @property
    def margin_x(self):
        return self.__margin[0]

    @property
    def margin_y(self):
        return self.__margin[1]

    def _with_file_validator(func):
        @wraps(func)
        def wrapper(inst, file):
            if not isinstance(file, ImageFont.ImageFont):
                if not os.path.exists(file):
                    raise ClaptchaError("%s doesn't exist" % (file,))
                if not os.path.isfile(file):
                    raise ClaptchaError("%s is not a file" % (file,))
            return func(inst, file)
        return wrapper

    @property
    def font(self):
        return self.__font

    @font.setter
    @_with_file_validator
    def font(self, font):
        if isinstance(font, ImageFont.ImageFont):
            self.__font = font
        else:
            fontsize = self.h - 2 * self.margin_x
            self.__font = ImageFont.truetype(font, fontsize)

    @property
    def noise(self):
        return self.__noise

    @noise.setter
    def noise(self, noise):
        if noise < 0. or noise > 1.:
            raise ClaptchaError("only acceptable noise amplitude from range [0:1]")
        self.__noise = noise

    def _writeText(self, image, text, pos):
        offset = 0
        x,y = pos

        for c in text:
            # Write letter
            c_size = self.font.getsize(c)
            c_image = Image.new('RGBA', c_size, (0,0,0,0))
            c_draw = ImageDraw.Draw(c_image)
            c_draw.text((0, 0), c, font=self.font, fill=(0,0,0,255))

            # Transform
            c_image = self._rndLetterTransform(c_image)

            # Paste onto image
            image.paste(c_image, (x+offset, y), c_image)
            offset += c_size[0]

    def _drawLine(self, image):
        w,h = image.size
        w *= 5
        h *= 5

        l_image = Image.new('RGBA', (w,h), (0,0,0,0))
        l_draw = ImageDraw.Draw(l_image)

        x1 = int(w * random.uniform(0, 0.1))
        y1 = int(h * random.uniform(0, 1))
        x2 = int(w * random.uniform(0.9, 1))
        y2 = int(h * random.uniform(0, 1))

        # Draw
        l_draw.line(((x1, y1), (x2, y2)), fill=(0, 0, 0, 255), width=12)

        # Transform
        l_image = self._rndLineTransform(l_image)
        l_image = l_image.resize(image.size, resample=self.resample)

        # Paste onto image
        image.paste(l_image, (0,0), l_image)

    def _whiteNoise(self, size):
        if self.noise > 0.003921569: # 1./255.
            w,h = size

            n_image = Image.new('RGB', size, (0,0,0,0))
            rnd_grid = map(lambda _: tuple([round(255 * random.uniform(1. - self.noise, 1.))]) * 3,
                           [0] * w * h)
            n_image.putdata(list(rnd_grid))
            return n_image
        else:
            return None

    def _rndLetterTransform(self, image):
        w,h = image.size

        dx = w * random.uniform(0.2, 0.7)
        dy = h * random.uniform(0.2, 0.7)

        x1, y1 = self.__class__._rndPointDisposition(dx, dy)
        x2, y2 = self.__class__._rndPointDisposition(dx, dy)

        w += abs(x1) + abs(x2)
        h += abs(x1) + abs(x2)

        quad = self.__class__._quadPoints((w,h), (x1,y1), (x2,y2))

        return image.transform(image.size, Image.QUAD,
                               data=quad, resample=self.resample)

    def _rndLineTransform(self, image):
        w,h = image.size

        dx = w * random.uniform(0.2, 0.5)
        dy = h * random.uniform(0.2, 0.5)
        
        x1, y1 = [abs(z) for z in self.__class__._rndPointDisposition(dx, dy)]
        x2, y2 = [abs(z) for z in self.__class__._rndPointDisposition(dx, dy)]

        quad = self.__class__._quadPoints((w,h), (x1,y1), (x2,y2))

        return image.transform(image.size, Image.QUAD,
                               data=quad, resample=self.resample)

    @staticmethod
    def _rndPointDisposition(dx, dy):
        x = int(random.uniform(-dx, dx))
        y = int(random.uniform(-dy, dy))
        return (x,y)

    @staticmethod
    def _quadPoints(size, disp1, disp2):
        w,h = size
        x1,y1 = disp1
        x2,y2 = disp2

        return (
            x1,    -y1,
            -x1,    h + y2,
            w + x2, h - y2,
            w - x2, y1
        )
