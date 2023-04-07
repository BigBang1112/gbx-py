import os
import sys
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTextEdit,
)
from PySide6.QtCore import Slot, QSize, Qt
from PySide6.QtGui import QTextCursor

from gbx_parser import GbxStruct, GbxStructWithoutBodyParsed
from construct import Container, ListContainer, RawCopy, Struct, Adapter, Subconstruct

from widgets.hex_editor import GbxHexEditor
from widgets.inspector import Inspector

from export_obj import export_obj


def container_iter(ctn):
    for key, value in ctn.items():
        if key != "_io":
            yield key, value


class QTreeWidgetItem_WithData(QTreeWidgetItem):
    def __init__(self, data, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gbx_data = data


def tree_widget_item(key, value):
    if isinstance(value, Container):
        item = QTreeWidgetItem([key])
        for child in container_iter(value):
            item.addChild(tree_widget_item(*child))

        return item
    elif isinstance(value, ListContainer):
        item = QTreeWidgetItem([key, f"Array({len(value)})"])

        for i, child in enumerate(value):
            item.addChild(tree_widget_item(str(i), child))

        return item
    else:
        return QTreeWidgetItem_WithData(
            Container(type=type(value).__name__, value=value),
            [key, type(value).__name__, str(value)],
        )


def GbxDataViewer(data, on_item_select):
    tree = QTreeWidget()
    tree.setColumnCount(3)
    tree.setHeaderLabels(["Name", "Type", "Value"])

    for key, value in container_iter(data):
        tree.addTopLevelItem(tree_widget_item(key, value))

    tree.expandToDepth(3)
    tree.resizeColumnToContents(0)
    tree.resizeColumnToContents(1)
    tree.resizeColumnToContents(2)

    @Slot()
    def on_item_double_clicked(item: QTreeWidgetItem, col):
        if isinstance(item, QTreeWidgetItem_WithData):
            if item.gbx_data.type == "bytes":
                on_item_select(item.gbx_data.value)

    tree.itemDoubleClicked.connect(on_item_double_clicked)

    return tree


def GbxEditorUi(raw_bytes, parsed_data):
    # window

    app = QApplication.instance() or QApplication(sys.argv)

    window = QMainWindow()
    window.resize(QSize(1600, 1000))

    # widgets

    inspector = Inspector()

    def on_select(raw_bytes):
        inspector.inspect(raw_bytes)

    hex_editor = GbxHexEditor(on_select)
    hex_editor.set_bytes(raw_bytes)

    def on_item_select(new_bytes):
        hex_editor.set_bytes(new_bytes)
        inspector.inspect(new_bytes)

    tree = GbxDataViewer(parsed_data, on_item_select)

    # layout

    layout_v = QVBoxLayout()
    layout_v.addWidget(hex_editor)
    layout_v.addWidget(inspector)

    layout_h = QHBoxLayout()
    layout_h.addWidget(tree)
    layout_h.addLayout(layout_v)

    widget = QWidget()
    widget.setLayout(layout_h)
    window.setCentralWidget(widget)
    window.show()
    # app.exec()

    return window


def wrapStruct(struct):
    if isinstance(struct, Struct):
        return RawCopy(Struct(*[wrapStruct(s) for s in struct.subcons]))
    else:
        return RawCopy(struct)


def construct_all_folders(all_folders, parent_folder_path, current_folder):
    for folder in current_folder.folders:
        all_folders.append(parent_folder_path + folder.name + "\\")
        construct_all_folders(all_folders, all_folders[-1], folder)


def create_custom_material(material_name):
    return Container(
        header=(Container(class_id=0x090FD000)),
        body=ListContainer(
            [
                Container(
                    chunk_id=0x090FD000,
                    chunk=Container(
                        version=11,
                        is_using_game_material=True,
                        material_name="",
                        model="",
                        base_texture="",
                        surface_physic_id=16,
                        surface_gameplay_id=0,
                        link="Stadium\\Media\\Material\\" + material_name,
                        csts=[],
                        color=[],
                        uv_anim=[],
                        u07=[],
                        user_textures=[],
                        hiding_group="",
                    ),
                ),
                Container(
                    chunk_id=0x090FD001,
                    chunk=Container(
                        version=5,
                        u01=-1,
                        tiling_u=0,
                        tiling_v=0,
                        texture_size=1.0,
                        u02=0,
                        is_natural=False,
                    ),
                ),
                Container(chunk_id=0x090FD002,
                          chunk=Container(version=0, u01=0)),
                Container(
                    chunk_id=0xFACADE01,
                ),
            ]
        ),
    )


def create_custom_material2(material_name):
    return Container(
        header=(Container(class_id=0x090FD000)),
        body=ListContainer(
            [
                Container(
                    chunk_id=0x090FD000,
                    chunk=Container(
                        version=11,
                        is_using_game_material=False,
                        material_name="TM_" + material_name + "_asset",
                        model="",
                        base_texture="",
                        surface_physic_id=6,
                        surface_gameplay_id=0,
                        link=material_name,
                        csts=[],
                        color=[],
                        uv_anim=[],
                        u07=[],
                        user_textures=[],
                        hiding_group="",
                    ),
                ),
                Container(
                    chunk_id=0x090FD001,
                    chunk=Container(
                        version=5,
                        u01=-1,
                        tiling_u=0,
                        tiling_v=0,
                        texture_size=1.0,
                        u02=0,
                        is_natural=False,
                    ),
                ),
                Container(chunk_id=0x090FD002,
                          chunk=Container(version=0, u01=0)),
                Container(
                    chunk_id=0xFACADE01,
                ),
            ]
        ),
    )


def parse_node(file_path, node_offset=0, path=None):
    if path is None:
        path = []
    depth = len(path)
    file_name = os.path.basename(file_path)
    path.append(file_name)

    with open(file_path, "rb") as f:
        raw_bytes = f.read()

        gbx_data = {}
        nodes = []
        data = GbxStruct.parse(raw_bytes, gbx_data=gbx_data, nodes=nodes)
        data.nodes = ListContainer(nodes)
        data.node_offset = node_offset
        data.path = path
        nb_nodes = len(data.nodes) - 1
        node_offset += len(data.nodes) - 1
        print("  " * depth + f"- {file_name} ({len(data.nodes) - 1} nodes)")

        # get all folders
        external_folders = data.reference_table.external_folders
        root_folder_name = os.path.dirname(file_path) + "\\"
        all_folders = [root_folder_name]
        if external_folders is not None:
            root_folder_name += "..\\" * external_folders.ancestor_level
            construct_all_folders(
                all_folders, root_folder_name, external_folders)

        # parse external nodes
        for external_node in data.reference_table.external_nodes:
            if external_node.ref.endswith(".Material.Gbx"):
                material_name = external_node.ref.split(".")[0]
                data.nodes[external_node.node_index] = create_custom_material2(
                    material_name
                )
                print(
                    "  " * (depth + 1) +
                    f"- {material_name} Material (1 custom node)"
                )
            else:
                # print(external_node)
                ext_node_data, nb_sub_nodes, win = parse_node(
                    all_folders[external_node.folder_index] +
                    external_node.ref,
                    node_offset,
                    path[:],
                )
                nb_nodes += nb_sub_nodes
                node_offset += nb_sub_nodes
                data.nodes[external_node.node_index] = ext_node_data
                data.nodes.extend(ext_node_data.nodes[1:])
                # if external_node.ref == "CactusE.HitShape.Gbx":
                #     app = QApplication.instance() or QApplication(sys.argv)
                #     app.exec()

        for i, n in enumerate(data.nodes):
            if n is not None and not "path" in n:
                n.path = f"{path} [node={i}]"

        data2 = GbxStructWithoutBodyParsed.parse(
            raw_bytes, gbx_data={}, nodes=[])
        data2.header.body_compression = "uncompressed"
        raw_bytes_uncompressed = GbxStructWithoutBodyParsed.build(
            data2, gbx_data={}, nodes=[]
        )

        return (
            data,
            nb_nodes,
            GbxEditorUi(raw_bytes, data),
        )


def generate_node(data):
    gbx_data = {}
    nodes = data.nodes[:]
    # data.header.body_compression = "uncompressed"
    new_bytes = GbxStruct.build(data, gbx_data=gbx_data, nodes=nodes)
    for n in nodes:
        if n is not None:
            print(f"node not referenced {n.path}")

    # check built node
    gbx_data = {}
    nodes = []
    new_data = GbxStruct.parse(new_bytes, gbx_data=gbx_data, nodes=nodes)
    new_data.nodes = ListContainer(nodes)

    data2 = GbxStructWithoutBodyParsed.parse(new_bytes, gbx_data={}, nodes=[])
    data2.header.body_compression = "uncompressed"
    new_bytes_uncompressed = GbxStructWithoutBodyParsed.build(
        data2, gbx_data={}, nodes=[]
    )

    return new_bytes, GbxEditorUi(new_bytes_uncompressed, new_data)


if __name__ == "__main__":
    file = "20_RectG_L32W32H05_#3.Item.Gbx"

    file = "Fall.Item.Gbx"
    file = "GateCheckpointCenter8mv2.Item.Gbx"
    file = "RampMedv2.Item.Gbx"
    file = "Z47_LoopStartCakeOut16_#7.Item.Gbx"
    file = "test_circle.Item.Gbx"
    file = "TunnelSupportPillarLarge16m.Item.Gbx"

    file = "Cactus.StaticObject.Gbx"
    file = "CactusMedium.Item.Gbx"
    file = "CactusB.StaticObject.Gbx"
    file = "Cactus.Mesh.Gbx"

    file = "C:\\Users\\schad\\Documents\\Trackmania\\Scripts\\test.Item.Gbx"
    file = "C:\\Users\\schad\\Documents\\Trackmania\\Scripts\\test_boost2.Item.Gbx"

    # file = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\RTCP.Item.Gbx"
    file = "C:\\Users\\schad\\OpenplanetNext\\Extract\\GameData\\Stadium\\Items\\CactusMedium.Item.Gbx"
    file = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\test_gbx2.Item.Gbx"
    file = "C:\\Users\\schad\\OpenplanetNext\\Extract\\GameData\\Stadium\\Media\\PlaceParam\\RoadSign.PlaceParam.Gbx"
    file = "C:\\Users\\schad\\OpenplanetNext\\Extract\\GameData\\Stadium\\Media\\PlaceParam\\TunnelSupport.PlaceParam.Gbx"
    file = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\test_circle.Item.Gbx"
    file = "C:\\Users\\schad\\OpenplanetNext\\Extract\\GameData\\Stadium\\Items\\CactusVerySmall.Item.Gbx"
    file = "C:\\Users\\schad\\OpenplanetNext\\Extract\\GameData\\Stadium\\Media\\Static\\Vegetation\\CactusE.Mesh.Gbx"
    # file = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\Eggs_4.Item.Gbx"
    data, nb_nodes, win = parse_node(file)
    print(f"total nodes: {nb_nodes}")

    # Export obj
    export_dir = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\"
    idx = 11
    vertices = data.nodes[idx+1].body[0].chunk.vertices_coords
    normals = data.nodes[idx+1].body[0].chunk.normals
    uv0 = data.nodes[idx+1].body[0].chunk.others.uv0
    indices = data.nodes[idx].body[8].chunk.index_buffer[0].chunk.indices
    obj_filepath = export_dir + os.path.basename(file).split(".")[0] + ".obj"
    print(obj_filepath)
    export_obj(obj_filepath, vertices,
               normals, uv0, indices, "ItemCactus")

    # file2 = "C:\\Users\\schad\\Documents\\Trackmania\\Items\\test_gbx1.Item.Gbx"
    # data2, nb_nodes2, win2 = parse_node(file2)

    # MODIFICATIONS

    # compression
    # data.header.body_compression = "compressed"

    # author
    # data.header.chunks.data[0].meta.id = ""
    # data.header.chunks.data[0].meta.author = "schadocalex"
    # data.header.chunks.data[0].catalog_position = 1

    # merge external nodes
    # data.header.num_nodes = nb_nodes + 1
    # data.reference_table.num_external_nodes = 0
    # data.reference_table.external_folders = None
    # data.reference_table.external_nodes = []

    # bypass variants?
    # data.body[12].chunk.entity_model = 2

    # lightmap
    # data.body[16].chunk.disable_lightmap = True

    # make mesh not collidable
    # data.nodes[2].body.collidable = False
    # data.nodes[2].body.collidable_ref = -1

    # bytes3, win3 = generate_node(data)
    # with open(
    #     "C:\\Users\\schad\\Documents\\Trackmania\\Items\\Export\\"
    #     + os.path.basename(file).replace(".Item", ".Item"),
    #     "wb",
    # ) as f:
    #     f.write(bytes3)

    app = QApplication.instance() or QApplication(sys.argv)
    app.exec()
