import argparse
import gc
import os

import numpy as np

from deepfloyd_if.modules import IFStageI, IFStageII, StableStageIII
from deepfloyd_if.modules.t5 import T5Embedder
from deepfloyd_if.pipelines.optimized_dream import run_stage1, run_stage2, run_stage3

import torch

import gradio as gr

from ui_files.utils import randomize_seed_fn, show_gallery_view, update_upscale_button, get_stage2_index, \
    check_if_stage2_selected, show_upscaled_view, get_device_map

try:
    import xformers

    os.environ["FORCE_MEM_EFFICIENT_ATTN"] = "1"
except:
    pass

device = torch.device(0)
if_I = IFStageI('IF-I-XL-v1.0', device=torch.device("cpu"))
if_I.to(torch.float16)  # half
# # if_II = IFStageII('IF-II-L-v1.0', device=torch.device("cpu"))
# # if_III = StableStageIII('stable-diffusion-x4-upscaler', device=torch.device("cpu"))
t5_device = torch.device(0)
t5 = T5Embedder(device=t5_device, t5_model_kwargs={"low_cpu_mem_usage": True,
                                                   "torch_dtype": torch.float16,
                                                   "device_map": get_device_map(t5_device),
                                                   "offload_folder": True})


def switch_devices(stage):
    if stage == 1:
        # t5.model.cpu()
        del t5.model
        if_I.to(torch.device(0))

    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def process_and_run_stage1(prompt,
                           negative_prompt,
                           seed_1,
                           num_images,
                           guidance_scale_1,
                           custom_timesteps_1,
                           num_inference_steps_1):
    print("Encoding prompts..")
    prompt = t5.get_text_embeddings(prompt)
    if negative_prompt == "":
        negative_prompt = torch.zeros_like(prompt)
    else:
        negative_prompt = t5.get_text_embeddings(negative_prompt)
    switch_devices(stage=1)
    prompt = prompt.to(if_I.device)
    negative_prompt = negative_prompt.to(if_I.device)
    print("Encoded. Running 1st stage")
    return run_stage1(
        if_I,
        t5_embs=prompt,
        negative_t5_embs=negative_prompt,
        seed=seed_1,
        num_images=num_images,
        guidance_scale_1=guidance_scale_1,
        custom_timesteps_1=custom_timesteps_1,
        num_inference_steps_1=num_inference_steps_1
    )


def create_ui(args):
    with gr.Blocks(css='ui_files/style.css') as demo:
        with gr.Box():
            with gr.Row(elem_id='prompt-container').style(equal_height=True):
                with gr.Column():
                    prompt = gr.Text(
                        label='Prompt',
                        show_label=False,
                        max_lines=1,
                        placeholder='Enter your prompt',
                        elem_id='prompt-text-input',
                    ).style(container=False)
                    negative_prompt = gr.Text(
                        label='Negative prompt',
                        show_label=False,
                        max_lines=1,
                        placeholder='Enter a negative prompt',
                        elem_id='negative-prompt-text-input',
                    ).style(container=False)
                generate_button = gr.Button('Generate').style(full_width=False)

            with gr.Column() as gallery_view:
                gallery = gr.Gallery(label='Stage 1 results',
                                     show_label=False,
                                     elem_id='gallery').style(
                    columns=args.GALLERY_COLUMN_NUM,
                    object_fit='contain')
                gr.Markdown('Pick your favorite generation to upscale.')
                with gr.Row():
                    upscale_to_256_button = gr.Button(
                        'Upscale to 256px',
                        visible=args.DISABLE_SD_X4_UPSCALER,
                        interactive=False)
                    upscale_button = gr.Button('Upscale',
                                               interactive=False,
                                               visible=not args.DISABLE_SD_X4_UPSCALER)
            with gr.Column(visible=False) as upscale_view:
                result = gr.Image(label='Result',
                                  show_label=False,
                                  type='filepath',
                                  interactive=False,
                                  elem_id='upscaled-image').style(height=640)
                back_to_selection_button = gr.Button('Back to selection')
            with gr.Accordion('Advanced options',
                              open=False,
                              visible=args.SHOW_ADVANCED_OPTIONS):
                with gr.Tabs():
                    with gr.Tab(label='Generation'):
                        seed_1 = gr.Slider(label='Seed',
                                           minimum=0,
                                           maximum=args.MAX_SEED,
                                           step=1,
                                           value=0)
                        randomize_seed_1 = gr.Checkbox(label='Randomize seed',
                                                       value=True)
                        guidance_scale_1 = gr.Slider(label='Guidance scale',
                                                     minimum=1,
                                                     maximum=20,
                                                     step=0.1,
                                                     value=7.0)
                        custom_timesteps_1 = gr.Dropdown(
                            label='Custom timesteps 1',
                            choices=[
                                'none',
                                'fast27',
                                'smart27',
                                'smart50',
                                'smart100',
                                'smart185',
                            ],
                            value="smart100",
                            visible=True)
                        num_inference_steps_1 = gr.Slider(
                            label='Number of inference steps',
                            minimum=1,
                            maximum=200,
                            step=1,
                            value=100,
                            visible=True)
                        num_images = gr.Slider(label='Number of images',
                                               minimum=1,
                                               maximum=4,
                                               step=1,
                                               value=4,
                                               visible=True)
                    with gr.Tab(label='Super-resolution 1'):
                        seed_2 = gr.Slider(label='Seed',
                                           minimum=0,
                                           maximum=args.MAX_SEED,
                                           step=1,
                                           value=0)
                        randomize_seed_2 = gr.Checkbox(label='Randomize seed',
                                                       value=True)
                        guidance_scale_2 = gr.Slider(label='Guidance scale',
                                                     minimum=1,
                                                     maximum=20,
                                                     step=0.1,
                                                     value=4.0)
                        custom_timesteps_2 = gr.Dropdown(
                            label='Custom timesteps 2',
                            choices=[
                                'none',
                                'fast27',
                                'smart27',
                                'smart50',
                                'smart100',
                                'smart185',
                            ],
                            value="smart50",
                            visible=True)
                        num_inference_steps_2 = gr.Slider(
                            label='Number of inference steps',
                            minimum=1,
                            maximum=200,
                            step=1,
                            value=50,
                            visible=True)
                    with gr.Tab(label='Super-resolution 2'):
                        seed_3 = gr.Slider(label='Seed',
                                           minimum=0,
                                           maximum=args.MAX_SEED,
                                           step=1,
                                           value=0)
                        randomize_seed_3 = gr.Checkbox(label='Randomize seed',
                                                       value=True)
                        guidance_scale_3 = gr.Slider(label='Guidance scale',
                                                     minimum=1,
                                                     maximum=20,
                                                     step=0.1,
                                                     value=9.0)
                        num_inference_steps_3 = gr.Slider(
                            label='Number of inference steps',
                            minimum=1,
                            maximum=200,
                            step=1,
                            value=40,
                            visible=True)
        with gr.Box():
            with gr.Row():
                with gr.Accordion(label='Hidden params'):
                    selected_index_for_stage2 = gr.Number(
                        label='Selected index for Stage 2', value=-1, precision=0)

        generate_button.click(
            process_and_run_stage1,
            [prompt,
             negative_prompt,
             seed_1,
             num_images,
             guidance_scale_1,
             custom_timesteps_1,
             num_inference_steps_1],
            gallery
        )

        gallery.select(
            fn=get_stage2_index,
            outputs=selected_index_for_stage2,
            queue=False,
        )
        #
        # selected_index_for_stage2.change(
        #     fn=update_upscale_button,
        #     inputs=selected_index_for_stage2,
        #     outputs=[
        #         upscale_button,
        #         upscale_to_256_button,
        #     ],
        #     queue=False,
        # )
        #
        # stage2_inputs = [
        #     stage1_result_path,
        #     selected_index_for_stage2,
        #     seed_2,
        #     guidance_scale_2,
        #     custom_timesteps_2,
        #     num_inference_steps_2,
        # ]
        #
        # upscale_to_256_button.click(
        #     fn=check_if_stage2_selected,
        #     inputs=selected_index_for_stage2,
        #     queue=False,
        # ).then(
        #     fn=randomize_seed_fn,
        #     inputs=[seed_2, randomize_seed_2],
        #     outputs=seed_2,
        #     queue=False,
        # ).then(
        #     fn=show_upscaled_view,
        #     outputs=[
        #         gallery_view,
        #         upscale_view,
        #     ],
        #     queue=False,
        # ).then(
        #     fn=run_stage2,
        #     inputs=stage2_inputs,
        #     outputs=result,
        #     api_name='upscale256',
        # )  # .success(
        # #     fn=upload_stage2_info,
        # #     inputs=[
        # #         stage1_param_file_hash_name,
        # #         result,
        # #         selected_index_for_stage2,
        # #         seed_2,
        # #         guidance_scale_2,
        # #         custom_timesteps_2,
        # #         num_inference_steps_2,
        # #     ],
        # #     queue=False,
        # # )
        #
        # stage2_3_inputs = [
        #     stage1_result_path,
        #     selected_index_for_stage2,
        #     seed_2,
        #     guidance_scale_2,
        #     custom_timesteps_2,
        #     num_inference_steps_2,
        #     prompt,
        #     negative_prompt,
        #     seed_3,
        #     guidance_scale_3,
        #     num_inference_steps_3,
        # ]
        #
        # upscale_button.click(
        #     fn=check_if_stage2_selected,
        #     inputs=selected_index_for_stage2,
        #     queue=False,
        # ).then(
        #     fn=randomize_seed_fn,
        #     inputs=[seed_2, randomize_seed_2],
        #     outputs=seed_2,
        #     queue=False,
        # ).then(
        #     fn=randomize_seed_fn,
        #     inputs=[seed_3, randomize_seed_3],
        #     outputs=seed_3,
        #     queue=False,
        # ).then(
        #     fn=show_upscaled_view,
        #     outputs=[
        #         gallery_view,
        #         upscale_view,
        #     ],
        #     queue=False,
        # ).then(
        #     fn=run_stage3,
        #     inputs=stage2_3_inputs,
        #     outputs=result,
        #     api_name='upscale1024',
        # )  # .success(
        # #     fn=upload_stage2_3_info,
        # #     inputs=[
        # #         stage1_param_file_hash_name,
        # #         result,
        # #         selected_index_for_stage2,
        # #         seed_2,
        # #         guidance_scale_2,
        # #         custom_timesteps_2,
        # #         num_inference_steps_2,
        # #         prompt,
        # #         negative_prompt,
        # #         seed_3,
        # #         guidance_scale_3,
        # #         num_inference_steps_3,
        # #     ],
        # #     queue=False,
        # # )
        #
        # back_to_selection_button.click(
        #     fn=show_gallery_view,
        #     outputs=[
        #         gallery_view,
        #         upscale_view,
        #     ],
        #     queue=False,
        # )
    return demo


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='IF UI settings')
    parser.add_argument('--GALLERY_COLUMN_NUM', type=int, default=4)
    parser.add_argument('--DISABLE_SD_X4_UPSCALER', type=bool, default=True)
    parser.add_argument('--SHOW_ADVANCED_OPTIONS', type=bool, default=True)
    parser.add_argument('--MAX_SEED', type=int, default=np.iinfo(np.int32).max)

    demo = create_ui(parser.parse_args())
    demo.launch()
