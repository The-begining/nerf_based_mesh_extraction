"""## 0. Install and Import modules
Ensure `torch` and `torchvision` are installed. If `pytorch3d` is not installed, install it using the following cell:
"""

import os
import sys
import torch
import subprocess
need_pytorch3d=False
try:
    import pytorch3d
except ModuleNotFoundError:
    need_pytorch3d=True
if need_pytorch3d:
    pyt_version_str=torch.__version__.split("+")[0].replace(".", "")
    version_str="".join([
        f"py3{sys.version_info.minor}_cu",
        torch.version.cuda.replace(".",""),
        f"_pyt{pyt_version_str}"
    ])
    !pip install iopath
    if sys.platform.startswith("linux"):
        print("Trying to install wheel for PyTorch3D")
        !pip install --no-index --no-cache-dir pytorch3d -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/{version_str}/download.html
        pip_list = !pip freeze
        need_pytorch3d = not any(i.startswith("pytorch3d==") for  i in pip_list)
    if need_pytorch3d:
        print(f"failed to find/install wheel for {version_str}")
if need_pytorch3d:
    print("Installing PyTorch3D from source")
    !pip install ninja
    !pip install 'git+https://github.com/facebookresearch/pytorch3d.git@stable'

# %matplotlib inline
# %matplotlib notebook
import os
import sys
import time
import json
import glob
import torch
import math
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from IPython import display
from tqdm.notebook import tqdm

# Data structures and functions for rendering
from pytorch3d.structures import Volumes
from pytorch3d.transforms import so3_exp_map
from pytorch3d.renderer import (
    FoVPerspectiveCameras,
    NDCMultinomialRaysampler,
    MonteCarloRaysampler,
    EmissionAbsorptionRaymarcher,
    ImplicitRenderer,
    RayBundle,
    ray_bundle_to_ray_points,
)

# obtain the utilized device
if torch.cuda.is_available():
    device = torch.device("cuda:0")
    torch.cuda.set_device(device)
else:
    print(
        'Please note that NeRF is a resource-demanding method.'
        + ' Running this notebook on CPU will be extremely slow.'
        + ' We recommend running the example on a GPU'
        + ' with at least 10 GB of memory.'
    )
    device = torch.device("cpu")


import os
import sys
# Verify if the path is added correctly
print(sys.path)

import importlib
import plot_image_grid
importlib.reload(plot_image_grid)

# Try to import the files
try:
    from plot_image_grid import image_grid
    from generate_cow_renders import generate_cow_renders
    print("Modules imported successfully.")
except ImportError as e:
    print(f"Error importing modules: {e}")

# Check if functions are accessible
print("Available functions:")
print(dir())  # This will list all the names in the current scope

# Optionally, try calling a function if you know it exists
try:
    # Replace 'some_function' with an actual function name from your module
    # Example: image_grid(some_arguments)
    print("Calling image_grid function:")
    # image_grid(...)  # Uncomment this line to call the function if you have arguments
except Exception as e:
    print(f"Error calling function: {e}")

#import os

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

# create the default data directory
#current_dir = os.path.dirname(os.path.realpath(__file__))
#DATA_DIR = os.path.join(current_dir, "..", "data", "cow_mesh")

# Set the data directory to the current directory
DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "dataset")
SUBFOLDER_PATH = os.path.join(DATA_DIR, 'pastry_new')  # Adjust this if 'pastry_new' is still relevant


# Define the names of your custom files
custom_obj_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_HQ-1K-JPG.obj")       # Path to the .obj file
custom_mtl_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_HQ-1K-JPG.mtl")     # Path to the .mtl file
custom_texture_file = os.path.join(SUBFOLDER_PATH, "3DPastry001_HQ-1K-JPG_Color.png")  # Path to the texture file

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
    custom_obj_path = os.path.join(data_dir, "3DPastry001_HQ-1K-JPG.obj")
    custom_mtl_path = os.path.join(data_dir, "3DPastry001_HQ-1K-JPG.mtl")
    custom_texture_path = os.path.join(data_dir, "3DPastry001_HQ-1K-JPG_Color.jpg")

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

target_cameras, target_images, target_silhouettes = generate_cow_renders(num_views=40, azimuth_range=180)
image_grid(target_images.clamp(0., 1.).cpu().numpy(), rows=3, cols=5, rgb=True, fill=True)
plt.show()



# render_size describes the size of both sides of the
# rendered images in pixels. Since an advantage of
# Neural Radiance Fields are high quality renders
# with a significant amount of details, we render
# the implicit function at double the size of
# target images.
render_size = target_images.shape[1] * 2

# Our rendered scene is centered around (0,0,0)
# and is enclosed inside a bounding box
# whose side is roughly equal to 3.0 (world units).
volume_extent_world = 3.0

# 1) Instantiate the raysamplers.

# Here, NDCMultinomialRaysampler generates a rectangular image
# grid of rays whose coordinates follow the PyTorch3D
# coordinate conventions.
raysampler_grid = NDCMultinomialRaysampler(
    image_height=render_size,
    image_width=render_size,
    n_pts_per_ray=128,
    min_depth=0.1,
    max_depth=volume_extent_world,
)

# MonteCarloRaysampler generates a random subset
# of `n_rays_per_image` rays emitted from the image plane.
raysampler_mc = MonteCarloRaysampler(
    min_x = -1.0,
    max_x = 1.0,
    min_y = -1.0,
    max_y = 1.0,
    n_rays_per_image=750,
    n_pts_per_ray=128,
    min_depth=0.1,
    max_depth=volume_extent_world,
)

# 2) Instantiate the raymarcher.
# Here, we use the standard EmissionAbsorptionRaymarcher
# which marches along each ray in order to render
# the ray into a single 3D color vector
# and an opacity scalar.
raymarcher = EmissionAbsorptionRaymarcher()

# Finally, instantiate the implicit renders
# for both raysamplers.
renderer_grid = ImplicitRenderer(
    raysampler=raysampler_grid, raymarcher=raymarcher,
)
renderer_mc = ImplicitRenderer(
    raysampler=raysampler_mc, raymarcher=raymarcher,
)

class HarmonicEmbedding(torch.nn.Module):
    def __init__(self, n_harmonic_functions=60, omega0=0.1):
        """
        Given an input tensor `x` of shape [minibatch, ... , dim],
        the harmonic embedding layer converts each feature
        in `x` into a series of harmonic features `embedding`
        as follows:
            embedding[..., i*dim:(i+1)*dim] = [
                sin(x[..., i]),
                sin(2*x[..., i]),
                sin(4*x[..., i]),
                ...
                sin(2**(self.n_harmonic_functions-1) * x[..., i]),
                cos(x[..., i]),
                cos(2*x[..., i]),
                cos(4*x[..., i]),
                ...
                cos(2**(self.n_harmonic_functions-1) * x[..., i])
            ]

        Note that `x` is also premultiplied by `omega0` before
        evaluating the harmonic functions.
        """
        super().__init__()
        self.register_buffer(
            'frequencies',
            omega0 * (2.0 ** torch.arange(n_harmonic_functions)),
        )
    def forward(self, x):
        """
        Args:
            x: tensor of shape [..., dim]
        Returns:
            embedding: a harmonic embedding of `x`
                of shape [..., n_harmonic_functions * dim * 2]
        """
        embed = (x[..., None] * self.frequencies).view(*x.shape[:-1], -1)
        return torch.cat((embed.sin(), embed.cos()), dim=-1)


class NeuralRadianceField(torch.nn.Module):
    def __init__(self, n_harmonic_functions=60, n_hidden_neurons=256):
        super().__init__()
        """
        Args:
            n_harmonic_functions: The number of harmonic functions
                used to form the harmonic embedding of each point.
            n_hidden_neurons: The number of hidden units in the
                fully connected layers of the MLPs of the model.
        """

        # The harmonic embedding layer converts input 3D coordinates
        # to a representation that is more suitable for
        # processing with a deep neural network.
        self.harmonic_embedding = HarmonicEmbedding(n_harmonic_functions)

        # The dimension of the harmonic embedding.
        embedding_dim = n_harmonic_functions * 2 * 3

        # self.mlp is a simple 2-layer multi-layer perceptron
        # which converts the input per-point harmonic embeddings
        # to a latent representation.
        # Not that we use Softplus activations instead of ReLU.
        self.mlp = torch.nn.Sequential(
            torch.nn.Linear(embedding_dim, n_hidden_neurons),
            torch.nn.Softplus(beta=10.0),
            torch.nn.Linear(n_hidden_neurons, n_hidden_neurons),
            torch.nn.Softplus(beta=10.0),
        )

        # Given features predicted by self.mlp, self.color_layer
        # is responsible for predicting a 3-D per-point vector
        # that represents the RGB color of the point.
        self.color_layer = torch.nn.Sequential(
            torch.nn.Linear(n_hidden_neurons + embedding_dim, n_hidden_neurons),
            torch.nn.Softplus(beta=10.0),
            torch.nn.Linear(n_hidden_neurons, 3),
            torch.nn.Sigmoid(),
            # To ensure that the colors correctly range between [0-1],
            # the layer is terminated with a sigmoid layer.
        )

        # The density layer converts the features of self.mlp
        # to a 1D density value representing the raw opacity
        # of each point.
        self.density_layer = torch.nn.Sequential(
            torch.nn.Linear(n_hidden_neurons, 1),
            torch.nn.Softplus(beta=10.0),
            # Sofplus activation ensures that the raw opacity
            # is a non-negative number.
        )

        # We set the bias of the density layer to -1.5
        # in order to initialize the opacities of the
        # ray points to values close to 0.
        # This is a crucial detail for ensuring convergence
        # of the model.
        self.density_layer[0].bias.data[0] = -1.5

        # Initialize attributes to store ray data
        self.lengths = None
        self.xys = None
        self.directions = None

    def _get_densities(self, features):
        """
        This function takes `features` predicted by `self.mlp`
        and converts them to `raw_densities` with `self.density_layer`.
        `raw_densities` are later mapped to [0-1] range with
        1 - inverse exponential of `raw_densities`.
        """
        raw_densities = self.density_layer(features)
        return 1 - (-raw_densities).exp()

    def _get_colors(self, features, rays_directions):
        """
        This function takes per-point `features` predicted by `self.mlp`
        and evaluates the color model in order to attach to each
        point a 3D vector of its RGB color.

        In order to represent viewpoint dependent effects,
        before evaluating `self.color_layer`, `NeuralRadianceField`
        concatenates to the `features` a harmonic embedding
        of `ray_directions`, which are per-point directions
        of point rays expressed as 3D l2-normalized vectors
        in world coordinates.
        """
        spatial_size = features.shape[:-1]

        # Normalize the ray_directions to unit l2 norm.
        rays_directions_normed = torch.nn.functional.normalize(
            rays_directions, dim=-1
        )

        # Obtain the harmonic embedding of the normalized ray directions.
        rays_embedding = self.harmonic_embedding(
            rays_directions_normed
        )

        # Expand the ray directions tensor so that its spatial size
        # is equal to the size of features.
        rays_embedding_expand = rays_embedding[..., None, :].expand(
            *spatial_size, rays_embedding.shape[-1]
        )

        # Concatenate ray direction embeddings with
        # features and evaluate the color model.
        color_layer_input = torch.cat(
            (features, rays_embedding_expand),
            dim=-1
        )
        return self.color_layer(color_layer_input)


    def forward(
        self,
        ray_bundle: RayBundle,
        **kwargs,
    ):
        """
        The forward function accepts the parametrizations of
        3D points sampled along projection rays. The forward
        pass is responsible for attaching a 3D vector
        and a 1D scalar representing the point's
        RGB color and opacity respectively.

        Args:
            ray_bundle: A RayBundle object containing the following variables:
                origins: A tensor of shape `(minibatch, ..., 3)` denoting the
                    origins of the sampling rays in world coords.
                directions: A tensor of shape `(minibatch, ..., 3)`
                    containing the direction vectors of sampling rays in world coords.
                lengths: A tensor of shape `(minibatch, ..., num_points_per_ray)`
                    containing the lengths at which the rays are sampled.

        Returns:
            rays_densities: A tensor of shape `(minibatch, ..., num_points_per_ray, 1)`
                denoting the opacity of each ray point.
            rays_colors: A tensor of shape `(minibatch, ..., num_points_per_ray, 3)`
                denoting the color of each ray point.
        """
        # Store ray data for future use
        self.lengths = ray_bundle.lengths
        self.xys = ray_bundle.xys
        self.directions = ray_bundle.directions


        # We first convert the ray parametrizations to world
        # coordinates with `ray_bundle_to_ray_points`.
        rays_points_world = ray_bundle_to_ray_points(ray_bundle)
        # rays_points_world.shape = [minibatch x ... x 3]

        # For each 3D world coordinate, we obtain its harmonic embedding.
        embeds = self.harmonic_embedding(
            rays_points_world
        )
        # embeds.shape = [minibatch x ... x self.n_harmonic_functions*6]

        # self.mlp maps each harmonic embedding to a latent feature space.
        features = self.mlp(embeds)
        # features.shape = [minibatch x ... x n_hidden_neurons]

        # Finally, given the per-point features,
        # execute the density and color branches.

        rays_densities = self._get_densities(features)
        # rays_densities.shape = [minibatch x ... x 1]

        rays_colors = self._get_colors(features, ray_bundle.directions)
        # rays_colors.shape = [minibatch x ... x 3]

        return rays_densities, rays_colors

    def batched_forward(
        self,
        ray_bundle: RayBundle,
        n_batches: int = 16,
        **kwargs,
    ):
        """
        This function is used to allow for memory efficient processing
        of input rays. The input rays are first split to `n_batches`
        chunks and passed through the `self.forward` function one at a time
        in a for loop. Combined with disabling PyTorch gradient caching
        (`torch.no_grad()`), this allows for rendering large batches
        of rays that do not all fit into GPU memory in a single forward pass.
        In our case, batched_forward is used to export a fully-sized render
        of the radiance field for visualization purposes.

        Args:
            ray_bundle: A RayBundle object containing the following variables:
                origins: A tensor of shape `(minibatch, ..., 3)` denoting the
                    origins of the sampling rays in world coords.
                directions: A tensor of shape `(minibatch, ..., 3)`
                    containing the direction vectors of sampling rays in world coords.
                lengths: A tensor of shape `(minibatch, ..., num_points_per_ray)`
                    containing the lengths at which the rays are sampled.
            n_batches: Specifies the number of batches the input rays are split into.
                The larger the number of batches, the smaller the memory footprint
                and the lower the processing speed.

        Returns:
            rays_densities: A tensor of shape `(minibatch, ..., num_points_per_ray, 1)`
                denoting the opacity of each ray point.
            rays_colors: A tensor of shape `(minibatch, ..., num_points_per_ray, 3)`
                denoting the color of each ray point.

        """

        # Parse out shapes needed for tensor reshaping in this function.
        n_pts_per_ray = ray_bundle.lengths.shape[-1]
        spatial_size = [*ray_bundle.origins.shape[:-1], n_pts_per_ray]

        # Split the rays to `n_batches` batches.
        tot_samples = ray_bundle.origins.shape[:-1].numel()
        batches = torch.chunk(torch.arange(tot_samples), n_batches)

        # For each batch, execute the standard forward pass.
        batch_outputs = [
            self.forward(
                RayBundle(
                    origins=ray_bundle.origins.view(-1, 3)[batch_idx],
                    directions=ray_bundle.directions.view(-1, 3)[batch_idx],
                    lengths=ray_bundle.lengths.view(-1, n_pts_per_ray)[batch_idx],
                    xys=None,
                )
            ) for batch_idx in batches
        ]

        # Concatenate the per-batch rays_densities and rays_colors
        # and reshape according to the sizes of the inputs.
        rays_densities, rays_colors = [
            torch.cat(
                [batch_output[output_i] for batch_output in batch_outputs], dim=0
            ).view(*spatial_size, -1) for output_i in (0, 1)
        ]
        return rays_densities, rays_colors

"""## 4. Helper functions

In this function we define functions that help with the Neural Radiance Field optimization.
"""

def huber(x, y, scaling=0.1):
    """
    A helper function for evaluating the smooth L1 (huber) loss
    between the rendered silhouettes and colors.
    """
    diff_sq = (x - y) ** 2
    loss = ((1 + diff_sq / (scaling**2)).clamp(1e-4).sqrt() - 1) * float(scaling)
    return loss

def sample_images_at_mc_locs(target_images, sampled_rays_xy):
    """
    Given a set of Monte Carlo pixel locations `sampled_rays_xy`,
    this method samples the tensor `target_images` at the
    respective 2D locations.

    This function is used in order to extract the colors from
    ground truth images that correspond to the colors
    rendered using `MonteCarloRaysampler`.
    """
    ba = target_images.shape[0]
    dim = target_images.shape[-1]
    spatial_size = sampled_rays_xy.shape[1:-1]
    # In order to sample target_images, we utilize
    # the grid_sample function which implements a
    # bilinear image sampler.
    # Note that we have to invert the sign of the
    # sampled ray positions to convert the NDC xy locations
    # of the MonteCarloRaysampler to the coordinate
    # convention of grid_sample.
    images_sampled = torch.nn.functional.grid_sample(
        target_images.permute(0, 3, 1, 2),
        -sampled_rays_xy.view(ba, -1, 1, 2),  # note the sign inversion
        align_corners=True
    )
    return images_sampled.permute(0, 2, 3, 1).view(
        ba, *spatial_size, dim
    )

def show_full_render(
    neural_radiance_field, camera,
    target_image, target_silhouette,
    loss_history_color, loss_history_sil,
):
    """
    This is a helper function for visualizing the
    intermediate results of the learning.

    Since the `NeuralRadianceField` suffers from
    a large memory footprint, which does not let us
    render the full image grid in a single forward pass,
    we utilize the `NeuralRadianceField.batched_forward`
    function in combination with disabling the gradient caching.
    This chunks the set of emitted rays to batches and
    evaluates the implicit function on one batch at a time
    to prevent GPU memory overflow.
    """

    # Prevent gradient caching.
    with torch.no_grad():
        # Render using the grid renderer and the
        # batched_forward function of neural_radiance_field.
        rendered_image_silhouette, _ = renderer_grid(
            cameras=camera,
            volumetric_function=neural_radiance_field.batched_forward
        )
        # Split the rendering result to a silhouette render
        # and the image render.
        rendered_image, rendered_silhouette = (
            rendered_image_silhouette[0].split([3, 1], dim=-1)
        )

    # Generate plots.
    fig, ax = plt.subplots(2, 3, figsize=(15, 10))
    ax = ax.ravel()
    clamp_and_detach = lambda x: x.clamp(0.0, 1.0).cpu().detach().numpy()
    ax[0].plot(list(range(len(loss_history_color))), loss_history_color, linewidth=1)
    ax[1].imshow(clamp_and_detach(rendered_image))
    ax[2].imshow(clamp_and_detach(rendered_silhouette[..., 0]))
    ax[3].plot(list(range(len(loss_history_sil))), loss_history_sil, linewidth=1)
    ax[4].imshow(clamp_and_detach(target_image))
    ax[5].imshow(clamp_and_detach(target_silhouette))
    for ax_, title_ in zip(
        ax,
        (
            "loss color", "rendered image", "rendered silhouette",
            "loss silhouette", "target image",  "target silhouette",
        )
    ):
        if not title_.startswith('loss'):
            ax_.grid("off")
            ax_.axis("off")
        ax_.set_title(title_)
    fig.canvas.draw(); fig.show()
    display.clear_output(wait=True)
    display.display(fig)
    return fig

# Paths for checkpoint files
checkpoint_path = "checkpoint_epoch_19900.pth"
final_model_path = "final_model.pth"

# Function to save checkpoint with ray bundle data
def save_checkpoint(model, optimizer, epoch, loss, path):
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss,
        'lengths': model.lengths,
        'xys': model.xys,
        'directions': model.directions
    }
    torch.save(checkpoint, path)
    print(f"Checkpoint saved at epoch {epoch}")

# Function to load checkpoint and ray data
def load_checkpoint(path, model, optimizer):
    checkpoint = torch.load(path)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    model.lengths = checkpoint['lengths']
    model.xys = checkpoint['xys']
    model.directions = checkpoint['directions']
    start_epoch = checkpoint['epoch']
    loss = checkpoint['loss']
    print(f"Checkpoint loaded: starting at epoch {start_epoch + 1} with loss {loss}")
    return start_epoch, loss

# First move all relevant variables to the correct device.
renderer_grid = renderer_grid.to(device)
renderer_mc = renderer_mc.to(device)
target_cameras = target_cameras.to(device)
target_images = target_images.to(device)
target_silhouettes = target_silhouettes.to(device)

# Set the seed for reproducibility
torch.manual_seed(1)

# Instantiate the radiance field model.
neural_radiance_field = NeuralRadianceField().to(device)

# Instantiate the Adam optimizer. We set its master learning rate to 1e-3.
lr = 1e-3
optimizer = torch.optim.Adam(neural_radiance_field.parameters(), lr=lr)

# We sample 6 random cameras in a minibatch. Each camera
# emits raysampler_mc.n_pts_per_image rays.
batch_size = 6

# 3000 iterations take ~20 min on a Tesla M40 and lead to
# reasonably sharp results. However, for the best possible
# results, we recommend setting n_iter=20000.
n_iter = 10000

# Init the loss history buffers.
loss_history_color, loss_history_sil = [], []

# Check if a checkpoint exists
if os.path.exists(checkpoint_path):
    # Load the checkpoint
    start_epoch, _ = load_checkpoint(checkpoint_path, neural_radiance_field, optimizer)
else:
    # Start from scratch if no checkpoint is found
    start_epoch = 0
    print("No checkpoint found. Starting training from epoch 0.")

# The main optimization loop.
for iteration in range(start_epoch +1, n_iter):
    # In case we reached the last 75% of iterations,
    # decrease the learning rate of the optimizer 10-fold.
    if iteration == round(n_iter * 0.75):
        print('Decreasing LR 10-fold ...')
        optimizer = torch.optim.Adam(
            neural_radiance_field.parameters(), lr=lr * 0.1
        )

    # Zero the optimizer gradient.
    optimizer.zero_grad()

    # Sample random batch indices.
    batch_idx = torch.randperm(len(target_cameras))[:batch_size]

    # Sample the minibatch of cameras.
    batch_cameras = FoVPerspectiveCameras(
        R = target_cameras.R[batch_idx],
        T = target_cameras.T[batch_idx],
        znear = target_cameras.znear[batch_idx],
        zfar = target_cameras.zfar[batch_idx],
        aspect_ratio = target_cameras.aspect_ratio[batch_idx],
        fov = target_cameras.fov[batch_idx],
        device = device,
    )

    # Evaluate the nerf model.
    rendered_images_silhouettes, sampled_rays = renderer_mc(
        cameras=batch_cameras,
        volumetric_function=neural_radiance_field
    )
    rendered_images, rendered_silhouettes = (
        rendered_images_silhouettes.split([3, 1], dim=-1)
    )

    # Compute the silhouette error as the mean huber
    # loss between the predicted masks and the
    # sampled target silhouettes.
    silhouettes_at_rays = sample_images_at_mc_locs(
        target_silhouettes[batch_idx, ..., None],
        sampled_rays.xys
    )
    sil_err = huber(
        rendered_silhouettes,
        silhouettes_at_rays,
    ).abs().mean()

    # Compute the color error as the mean huber
    # loss between the rendered colors and the
    # sampled target images.
    colors_at_rays = sample_images_at_mc_locs(
        target_images[batch_idx],
        sampled_rays.xys
    )
    color_err = huber(
        rendered_images,
        colors_at_rays,
    ).abs().mean()

    # The optimization loss is a simple
    # sum of the color and silhouette errors.
    loss = color_err + sil_err

    # Log the loss history.
    loss_history_color.append(float(color_err))
    loss_history_sil.append(float(sil_err))

    # Every 10 iterations, print the current values of the losses.
    if iteration % 10 == 0:
        print(
            f'Iteration {iteration:05d}:'
            + f' loss color = {float(color_err):1.2e}'
            + f' loss silhouette = {float(sil_err):1.2e}'
        )

    # Take the optimization step.
    loss.backward()
    optimizer.step()


    # Real-time rendering preview every 100 iterations
    if iteration % 100 == 0:

        #save the model at the checkpoint
        save_checkpoint(neural_radiance_field, optimizer, iteration, loss, path=f"checkpoint_epoch_{iteration}.pth")

        # Render and display preview using the show_full_render function
        show_idx = torch.randperm(len(target_cameras))[:1]
        fig = show_full_render(
            neural_radiance_field,
            FoVPerspectiveCameras(
                R=target_cameras.R[show_idx],
                T=target_cameras.T[show_idx],
                znear=target_cameras.znear[show_idx],
                zfar=target_cameras.zfar[show_idx],
                aspect_ratio=target_cameras.aspect_ratio[show_idx],
                fov=target_cameras.fov[show_idx],
                device=device,
            ),
            target_images[show_idx][0],
            target_silhouettes[show_idx][0],
            loss_history_color,
            loss_history_sil,
        )
        plt.show()

torch.save(neural_radiance_field.state_dict(), "final_model.pth")
print("Final model saved.")

"""## 6. Visualizing the optimized neural radiance field

Finally, we visualize the neural radiance field by rendering from multiple viewpoints that rotate around the volume's y-axis.
"""

def generate_rotating_nerf(neural_radiance_field, n_frames = 50):
    logRs = torch.zeros(n_frames, 3, device=device)
    logRs[:, 1] = torch.linspace(-3.14, 3.14, n_frames, device=device)
    Rs = so3_exp_map(logRs)
    Ts = torch.zeros(n_frames, 3, device=device)
    Ts[:, 2] = 2.7
    frames = []
    print('Rendering rotating NeRF ...')
    for R, T in zip(tqdm(Rs), Ts):
        camera = FoVPerspectiveCameras(
            R=R[None],
            T=T[None],
            znear=target_cameras.znear[0],
            zfar=target_cameras.zfar[0],
            aspect_ratio=target_cameras.aspect_ratio[0],
            fov=target_cameras.fov[0],
            device=device,
        )
        # Note that we again render with `NDCMultinomialRaysampler`
        # and the batched_forward function of neural_radiance_field.
        frames.append(
            renderer_grid(
                cameras=camera,
                volumetric_function=neural_radiance_field.batched_forward,
            )[0][..., :3]
        )
    return torch.cat(frames)

with torch.no_grad():
    rotating_nerf_frames = generate_rotating_nerf(neural_radiance_field, n_frames=3*5)

image_grid(rotating_nerf_frames.clamp(0., 1.).cpu().numpy(), rows=3, cols=5, rgb=True, fill=True)
plt.show()

import torch
from skimage import measure
from pytorch3d.structures import Meshes
from pytorch3d.renderer import TexturesVertex

def extract_mesh_from_nerf(neural_radiance_field, grid_resolution=64):
    """
    Extracts a 3D mesh from NeRF using the Marching Cubes algorithm with PyTorch3D.

    Args:
        neural_radiance_field: The trained NeRF model.
        grid_resolution: Resolution of the 3D grid for Marching Cubes.

    Returns:
        A PyTorch3D Meshes object.
    """
    # Create a grid of points in 3D space
    x = torch.linspace(-1, 1, grid_resolution)
    y = torch.linspace(-1, 1, grid_resolution)
    z = torch.linspace(-1, 1, grid_resolution)
    #grid = torch.stack(torch.meshgrid(x, y, z), dim=-1).to(device)
    grid = torch.stack(torch.meshgrid(x, y, z, indexing="ij"), dim=-1).to(device)

    lengths = neural_radiance_field.lengths
    xys = neural_radiance_field.xys
    directions = neural_radiance_field.directions


    # If actual values are not provided, default to dummy values
    if lengths is None:
        lengths = torch.ones(*grid.shape[:-1], 1, device=grid.device)  # 1 is an example; adjust as needed
    if xys is None:
        xys = torch.zeros(*grid.shape[:-1], 2, device=grid.device)
    if directions is None:
        directions = torch.zeros_like(grid)
    # Print shapes to troubleshoot
    print("Grid shape:", grid.shape)
    print("Lengths shape before reshaping:", lengths.shape)
    print("Directions shape before reshaping:", directions.shape)
    print("Xys shape before reshaping:", xys.shape)


        # Ensure loaded tensors have compatible shapes with grid
    if lengths.shape == (4096, 128):  # The expected shape of `lengths`
        # Flatten the grid to a 1D tensor to match the ray count
        num_rays = grid.numel() // 3  # Number of rays in the grid
        # Reshape the lengths tensor to match the grid size
        lengths = lengths.view(num_rays, -1)  # reshape to match ray count, (num_rays, 128)
        # Take the last sample along each ray
        lengths = lengths[:, -1].unsqueeze(-1)  # Get the last point from each ray
        lengths = lengths.view(*grid.shape[:-1], 1).to(device)  # Reshape to match grid's shape

    elif lengths.shape != grid.shape[:-1] + (1,):
        raise ValueError(f"Unexpected shape for lengths: {lengths.shape}")



    # Ensure loaded tensors have compatible shapes with grid
    # Ensure `directions` matches the grid shape
    if directions.numel() < grid.numel():
        # Replicate `directions` if it is smaller than required
        repetitions = grid.numel() // directions.numel()
        directions = directions.repeat(repetitions, 1)[:grid.numel(), :].to(device)
        directions = directions.view(*grid.shape[:-1], 3).to(device)
    elif directions.shape == (4096, 3):
        num_rays = grid.numel() // 3  # Number of rays in the grid
        directions = directions.view(num_rays, 3).to(device)
        directions = directions.view(*grid.shape[:-1], 3).to(device)
    elif directions.shape != grid.shape:
        raise ValueError(f"Unexpected shape for directions: {directions.shape}")

        # Ensure `xys` matches the grid shape
    if xys.shape != grid.shape[:-1] + (2,):
        if xys.numel() < grid.numel():
            # Replicate `xys` if it is smaller than required
            repetitions = grid.numel() // xys.numel()
            xys = xys.repeat(repetitions, 1)[:grid.numel(), :].to(device)
            xys = xys.view(*grid.shape[:-1], 2).to(device)
        elif xys.shape == (4096, 2):
            num_rays = grid.numel() // 3  # Number of rays in the grid
            xys = xys.view(num_rays, 2).to(device)
            xys = xys.view(*grid.shape[:-1], 2).to(device)
        else:
            raise ValueError(f"Unexpected shape for xys: {xys.shape}")





      # Print shapes to troubleshoot
    print("Lengths shape after reshaping:", lengths.shape)
    print("Directions shape after reshaping:", directions.shape)
    print("Xys shape after reshaping:", xys.shape)

    # Define dummy values for lengths and xys that match the required shape
    """
    grid_shape = grid.shape[:-1]
    num_points_per_ray = 1  # Adjust if necessary based on your implementation

    # Example values for lengths and xys (adjust shape if needed)
    lengths = torch.ones(*grid_shape, num_points_per_ray, device=grid.device)
    xys = torch.zeros(*grid_shape, 2, device=grid.device)"""

    # Pass grid points through NeRF to get densities
    ray_bundle = RayBundle(
        origins=grid,
        directions=torch.zeros_like(grid),
        lengths=lengths,
        xys=xys
    )
    densities, _ = neural_radiance_field(ray_bundle)

    # Convert densities to a numpy array for Marching Cubes
    # Convert densities to a numpy array for Marching Cubes
    density_field = densities.squeeze().detach().cpu().numpy()
    print("Density field range:", density_field.min(), density_field.max())

    level = (density_field.min() + density_field.max()) / 2
    vertices, faces, normals, values = measure.marching_cubes(density_field, level=level)

    # Use Marching Cubes to extract vertices and faces
    #vertices, faces, normals, values = measure.marching_cubes(density_field, level=0.5)

    """# Convert vertices and faces to tensors
    vertices = torch.tensor(vertices, dtype=torch.float32).to(device)
    faces = torch.tensor(faces, dtype=torch.int64).to(device)"""
    # Convert vertices and faces to tensors, ensuring no negative strides
    vertices = torch.tensor(vertices.copy(), dtype=torch.float32).to(device)
    faces = torch.tensor(faces.copy(), dtype=torch.int64).to(device)


    # Create a texture for the mesh (e.g., white color for simplicity)
    textures = TexturesVertex(verts_features=torch.ones_like(vertices)[None])  # [1, V, 3] white color

    # Create a PyTorch3D Meshes object
    mesh = Meshes(verts=[vertices], faces=[faces], textures=textures)

    return mesh

# Example usage after training:
mesh = extract_mesh_from_nerf(neural_radiance_field)

import os

def save_mesh_with_pytorch3d(mesh, file_path):
    """
    Save a PyTorch3D Meshes object to an OBJ file without external libraries.

    Args:
        mesh: PyTorch3D Meshes object.
        file_path: Path where the OBJ file will be saved.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Extract vertices and faces
    vertices = mesh.verts_packed().detach().cpu()
    faces = mesh.faces_packed().detach().cpu()

    # Open file and write in OBJ format
    with open(file_path, "w") as f:
        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")

        # Write faces (OBJ uses 1-based indexing)
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

    print(f"Mesh saved to {file_path}")

# Example usage:
file_path = "output/nerf_mesh.obj"
save_mesh_with_pytorch3d(mesh, file_path)

from pytorch3d.renderer import MeshRenderer, MeshRasterizer, SoftPhongShader, PerspectiveCameras, RasterizationSettings
from pytorch3d.renderer.lighting import PointLights

# Set up the camera
cameras = PerspectiveCameras(device=device)

# Set up the renderer
raster_settings = RasterizationSettings(
    image_size=512,
    blur_radius=0.0,
    faces_per_pixel=1,
)
lights = PointLights(device=device, location=[[0.0, 0.0, -3.0]])
renderer = MeshRenderer(
    rasterizer=MeshRasterizer(cameras=cameras, raster_settings=raster_settings),
    shader=SoftPhongShader(device=device, cameras=cameras, lights=lights)
)

# Render the mesh
image = renderer(mesh)
plt.imshow(image[0, ..., :3].cpu().numpy())
plt.axis("off")
plt.show()

from pytorch3d.ops import sample_points_from_meshes

import torch
from pytorch3d.loss import chamfer_distance
from pytorch3d.io import load_objs_as_meshes

def compare_meshes(original_mesh_file, saved_mesh_file, device):
    """
    Compare the original mesh to a saved mesh file using Chamfer Distance.

    Args:
        original_mesh_file: Path to the original OBJ file.
        saved_mesh_file: Path to the saved OBJ file.
        device: The device to perform computations on.

    Returns:
        chamfer_loss: Chamfer Distance between the two meshes.
    """
    # Load the original and saved meshes
    original_mesh = load_objs_as_meshes([original_mesh_file], device=device)
    saved_mesh = load_objs_as_meshes([saved_mesh_file], device=device)


    print(f"Number of vertices: {original_mesh.num_verts_per_mesh()}")
    print(f"Number of faces: {original_mesh.num_faces_per_mesh()}")

    # Sample points from both meshes
    original_points = sample_points_from_meshes(original_mesh, num_samples=10000)
    saved_points = sample_points_from_meshes(saved_mesh, num_samples=10000)

    # Compute Chamfer Distance
    chamfer_loss, _ = chamfer_distance(original_points, saved_points)

    print(f"Chamfer Distance: {chamfer_loss.item()}")
    return chamfer_loss

# Usage
os.makedirs("output", exist_ok=True)

original_mesh_file = os.path.join(DATA_DIR, "pastry_new", "3DPastry001_HQ-1K-JPG.obj")
saved_mesh_file = "output/nerf_mesh.obj"         # Path to the saved mesh

compare_meshes(original_mesh_file, saved_mesh_file, device)