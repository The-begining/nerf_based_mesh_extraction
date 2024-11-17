# **NeRF Based Mesh Extraction**

[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

---

## **Features**

- Implements Neural Radiance Fields (NeRF) using PyTorch3D.
- Supports rendering and extracting 3D meshes.
- Provides visualization tools for rendered and extracted data.
- Modular and easy-to-customize code structure.

---

## **Installation**

### Prerequisites

Ensure you have Python 3.9+ installed on your system.

### Steps

1. Clone this repository:

   ```bash
   git clone https://github.com/The-begining/nerf_based_mesh_extraction.git
   cd nerf_based_mesh_extraction
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## **Usage**

### Running the Code

1. Place your dataset in the `dataset` folder:

   ```
   dataset/
   ├── pastry_new/
       ├── 3DPastry001_HQ-1K-JPG.obj
       ├── 3DPastry001_HQ-1K-JPG.mtl
       └── 3DPastry001_HQ-1K-JPG_Color.png
   ```

2. Run the main script:

   ```bash
   python script.py
   ```

3. The following outputs will be saved:
   - **Checkpoints**: Saved in the `saved` folder.
   - **Rendered Models**: Displayed in visualizations.
   - **Extracted Mesh**: Saved as `nerf_mesh.obj` in the `output` folder.

---

## **File Structure**

```
project/
├── script.py                 # Main script
├── dataset/                  # Dataset folder
│   └── pastry_new/           # Example subfolder
├── saved/                    # Folder for checkpoints and models
├── output/                   # Folder for extracted meshes
├── requirements.txt          # Dependencies
└── README.md                 # Project information
```

## **Real_time_rendering**

```
Real_time_rendering.ipynb file uses the pretrained model to showcase, that how rendering happens and our mesh extraction model to extract the mesh.
Limitation of resources hindered the process of the testing the model to its full potential.
However we tested with two different images and the result were satisfactory.

- Notebook can be found in root directory
- Image can be found in dataset folder
- Results can be found in output folder
```

---

## **Examples**

- Render visualizations:
  ```python
  python script.py
  ```
- Extract a 3D mesh and save it as an OBJ file:
  - Mesh files are saved in the `output` folder automatically.

---

## **Contributing**

Contributions are welcome! Feel free to fork out this project and submit pull requests.

---

## **License**

MIT License.

---

## **Contact**
<<<<<<< HEAD

For questions or suggestions, please contact [Shamimeh](mailto:shamimehmohajeri@gmail.com).
=======
For questions or suggestions, please contact:  
- [Shamimeh](mailto:shamimehmohajeri@gmail.com)  
- [Shubham Singh](mailto:softengg.shubham@gmail.com)  
- [Vaskar Shrestha](mailto:vasstha01@gmail.com)
>>>>>>> 3c48a8c318d12f93b1a778cad0cc93c5de0e8bea
