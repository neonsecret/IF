# -*- coding: utf-8 -*-
import diffusers
from diffusers import DiffusionPipeline, DDPMScheduler
import torch
import os

from .base import IFBaseModule
import packaging.version as pv


class StableStageIII(IFBaseModule):
    available_models = ['stable-diffusion-x4-upscaler']

    def __init__(self, *args, model_kwargs=None, pil_img_size=1024, **kwargs):
        super().__init__(*args, pil_img_size=pil_img_size, **kwargs)
        if pv.parse(diffusers.__version__) <= pv.parse('0.15.1'):
            raise ValueError(
                'Make sure to have `diffusers >= 0.16.0` installed.'
                ' Please run `pip install diffusers --upgrade`'
            )

        model_id = 'stabilityai' + "/" + self.dir_or_name.strip()

        model_kwargs = model_kwargs or {}
        precision = str(model_kwargs.get('precision', '16'))
        if precision == '16':
            torch_dtype = torch.float16
        elif precision == 'bf16':
            torch_dtype = torch.bfloat16
        else:
            torch_dtype = torch.float32

        self.model = DiffusionPipeline.from_pretrained(model_id, torch_dtype=torch_dtype, token=self.hf_token)
        self.model.to(self.device)

        # if bool(os.environ.get('FORCE_MEM_EFFICIENT_ATTN')):
        self.model.enable_xformers_memory_efficient_attention()

    @property
    def use_diffusers(self):
        if self.dir_or_name == self.available_models[-1]:
            return True
        elif os.path.isdir(self.dir_or_name) and os.path.isfile(os.path.join(self.dir_or_name, 'model_index.json')):
            return True
        return False

    def embeddings_to_image(
            self, low_res, prompt, style_t5_embs=None, positive_t5_embs=None, negative_t5_embs=None, batch_repeat=1,
            aug_level=0.0, blur_sigma=None, dynamic_thresholding_p=0.95, dynamic_thresholding_c=1.0, positive_mixer=0.5,
            sample_loop='ddpm', sample_timestep_respacing='75', guidance_scale=4.0, img_scale=4.0,
            progress=True, seed=None, sample_fn=None, device=None, **kwargs):

        if sample_loop == 'ddpm':
            self.model.scheduler = DDPMScheduler.from_config(self.model.scheduler.config)
        else:
            raise ValueError(f"For now only the 'ddpm' sample loop type is supported, but you passed {sample_loop}")

        num_inference_steps = int(sample_timestep_respacing)

        self.model.set_progress_bar_config(disable=not progress)

        generator = torch.manual_seed(seed)
        metadata = {
            'image': low_res,  # 1 3 256 256
            'prompt': prompt,
            'generator': generator,
            'guidance_scale': guidance_scale,
            'num_inference_steps': num_inference_steps,
            'output_type': 'pt',
        }

        images = self.model(**metadata).images

        sample = self._IFBaseModule__validate_generations(images)

        return sample, metadata

    def to(self, x):
        self.model.to(x)
