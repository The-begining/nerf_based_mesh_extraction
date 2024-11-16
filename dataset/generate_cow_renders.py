# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import os

import numpy as np
import torch
from pytorch3d.io import load_objs_as_meshes
from pytorch3d.renderer import (
    BlendParams,
    FoVPerspectiveCameras,
    look_at_view_transform,
    MeshRasterizer,
    MeshRenderer,
    PointLights,
    RasterizationSettings,
    SoftPhongShader,
    SoftSilhouetteShader,
)
import imageio
import matplotlib.pyplot as plt

from plot_image_grid import image_grid

# create the default data directory
#current_dir = os.path.dirname(os.path.realpath(__file__))
#DATA_DIR = os.path.join(current_dir, "..", "data", "cow_mesh")

# Set the data directory to the current directory
DATA_DIR = os.path.dirname(os.path.realpath('/content/drive/MyDrive/nerf/'))

# Define the path to the subfolder where your files are stored
SUBFOLDER_PATH = os.path.join(DATA_DIR, 'pastry_new')  

# Define the names of your custom files
custom_obj_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_LQ-1K-JPG.obj")       # Path to the .obj file
custom_mtl_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_LQ-1K-JPG.mtl")     # Path to the .mtl file
custom_texture_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_LQ-1K-JPG_Color.png")  # Path to the texture file

# You can now use these paths in your code
print("OBJ file path:", custom_obj_file)
print("MTL file path:", custom_mtl_file)
print("Texture file path:", custom_texture_file)


def generate_cow_renders(
    num_views: int = 40, data_dir: str = SUBFOLDER_PATH, azimuth_range: float = 180
):
    """
    This function generates `num_views` renders of a mesh.
    The renders are generated from viewpoints sampled at uniformly distributed
    azimuth intervals. The elevation is kept constant so that the camera's
    vertical position coincides with the equator.

    Args:
        num_views: The number of generated renders.
        data_dir: The folder that contains the mesh files. It expects an
            obj file, mtl file, and texture file in this directory.
        azimuth_range: number of degrees on each side of the start position to
            take samples.

    Returns:
        cameras: A batch of `num_views` `FoVPerspectiveCameras` from which the
            images are rendered.
        images: A tensor of shape `(num_views, height, width, 3)` containing
            the rendered images.
        silhouettes: A tensor of shape `(num_views, height, width)` containing
            the rendered silhouettes.
    """

    # Define the paths to the mesh files
    custom_obj_path = os.path.join(data_dir, "3DPastry001_LQ-1K-JPG.obj")
    custom_mtl_path = os.path.join(data_dir, "3DPastry001_LQ-1K-JPG.mtl")
    custom_texture_path = os.path.join(data_dir, "3DPastry001_LQ-1K-JPG_Color.jpg")

    # Check if the mesh files exist
    if not os.path.isfile(custom_obj_path) or not os.path.isfile(custom_mtl_path):
        raise FileNotFoundError("One or more mesh files do not exist in the specified directory.")

    # Setup device for rendering
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
    else:
        device = torch.device("cpu")

    # Load the OBJ file and associated material
    mesh = load_objs_as_meshes([custom_obj_path], device=device)

    # Normalize and center the target mesh
    verts = mesh.verts_packed()
    N = verts.shape[0]
    center = verts.mean(0)
    scale = max((verts - center).abs().max(0)[0])
    mesh.offset_verts_(-(center.expand(N, 3)))
    mesh.scale_verts_((1.0 / float(scale)))

    # Create a batch of viewing angles
    elev = torch.linspace(0, 0, num_views)  # Keep elevation constant
    azim = torch.linspace(-azimuth_range, azimuth_range, num_views) + 180.0

    # Setup lighting
    lights = PointLights(device=device, location=[[0.0, 0.0, -3.0]])

    # Initialize the camera
    R, T = look_at_view_transform(dist=2.7, elev=elev, azim=azim)
    cameras = FoVPerspectiveCameras(device=device, R=R, T=T)

    # Set up rasterization settings
    raster_settings = RasterizationSettings(image_size=128, blur_radius=0.0, faces_per_pixel=1)
    blend_params = BlendParams(sigma=1e-4, gamma=1e-4, background_color=(0.0, 0.0, 0.0))
    
    # Create the renderer
    renderer = MeshRenderer(
        rasterizer=MeshRasterizer(cameras=cameras, raster_settings=raster_settings),
        shader=SoftPhongShader(device=device, cameras=cameras, lights=lights, blend_params=blend_params),
    )

    # Create a batch of meshes by repeating the original mesh
    meshes = mesh.extend(num_views)

    # Render the mesh from each viewing angle
    target_images = renderer(meshes, cameras=cameras, lights=lights)

    # Silhouette rendering setup
    raster_settings_silhouette = RasterizationSettings(
        image_size=128, blur_radius=np.log(1.0 / 1e-4 - 1.0) * 1e-4, faces_per_pixel=50
    )
    renderer_silhouette = MeshRenderer(
        rasterizer=MeshRasterizer(cameras=cameras, raster_settings=raster_settings_silhouette),
        shader=SoftSilhouetteShader(),
    )

    # Render silhouettes
    silhouette_images = renderer_silhouette(meshes, cameras=cameras, lights=lights)
    silhouette_binary = (silhouette_images[..., 3] > 1e-4).float()

    return cameras, target_images[..., :3], silhouette_binary


#target_cameras, target_images, target_silhouettes = generate_cow_renders(num_views=40, azimuth_range=180)
#image_grid(target_images.clamp(0., 1.).cpu().numpy(), rows=3, cols=5, rgb=True, fill=True)
#plt.show()