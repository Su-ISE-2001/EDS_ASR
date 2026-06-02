import time
from pathlib import Path
from typing import Optional, List
import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd
import pyautogui
from autoscript_sdb_microscope_client import SdbMicroscopeClient
from autoscript_sdb_microscope_client.enumerations import *
from autoscript_sdb_microscope_client.structures import *
import autoscript_toolkit.vision as vision_toolkit
from logging import Logger

from matplotlib import pyplot as plt


def sem_active_view(sem: SdbMicroscopeClient, view_i: int, logger: Logger):
    logger.info(f"Activating view {view_i}...")
    sem.imaging.set_active_view(view_i)
    logger.info(f"Active view is now view {sem.imaging.get_active_view()}")


def sem_beam_switch(sem: SdbMicroscopeClient, opt: str, logger: Logger):
    logger.info(f"Turning electron beam {opt}...")
    if opt == 'on':
        if not sem.beams.electron_beam.is_on:
            sem.beams.electron_beam.turn_on()
    else:
        if sem.beams.electron_beam.is_on:
            sem.beams.electron_beam.turn_off()
    logger.info("Beam is now %s" % ("on" if sem.beams.electron_beam.is_on else "off"))


def sem_set_scan_params(sem: SdbMicroscopeClient, logger: Logger, mag: float, resolution: tuple[int,int], dwell: Optional[float]):
    screen_width = 0.127  # Polaroid standard
    sem.beams.electron_beam.horizontal_field_width.value = screen_width / mag
    logger.info(f"Setting sem magnification:{mag}")
    res_str = f"{resolution[0]}x{resolution[1]}"
    if res_str not in ScanningResolution.get_all_items():
        logger.warning(f"Resolution {resolution} is not supported, use 1536X1024 instead!!!")
        res_str = ScanningResolution.PRESET_1536X1024
    sem.beams.electron_beam.scanning.resolution.value = res_str
    logger.info(f"Setting sem resolution:{res_str}")
    sem.beams.electron_beam.scanning.mode.set_full_frame()
    logger.info(f"Setting sem scan mode: full frame")
    if dwell:
        sem.beams.electron_beam.scanning.dwell_time.value = dwell
        logger.info(f"Setting sem dwell:{dwell}")
    sem.beams.electron_beam.scanning.line_integration = 2


def sem_grab_scan_frame(sem: SdbMicroscopeClient, logger: Logger,
                        resolution: Optional[tuple[int,int]], dwell: Optional[float],
                        save_dir: str, prefix: str):
    sem_active_view(sem=sem, view_i=1, logger=logger)
    if resolution:
        res_str = f"{resolution[0]}x{resolution[1]}"
        if res_str not in ScanningResolution.get_all_items():
            logger.warning(f"Resolution {resolution} is not supported, use 1536X1024 instead!!!")
            res_str = ScanningResolution.PRESET_1536X1024
        logger.info(f"Setting sem resolution:{res_str}")
    else:
        res_str = sem.beams.electron_beam.scanning.resolution.value
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    tif_path = rf"{save_dir}/{prefix}.tif"
    settings = GrabFrameSettings(
        resolution=res_str,
        dwell_time=dwell if dwell else sem.beams.electron_beam.scanning.dwell_time.value,
        bit_depth=16,
        line_integration=2,
        # frame_integration=1,
        drift_correction=False,
    )
    logger.info(f'[{prefix}] Begin grab sem frame...')
    image = sem.imaging.grab_frame(settings)
    # Create databar items configuration
    databar_config = ["beam icon", "date", "wd", "hfw", "hv", "detector type", "dwell", "micronbar"]

    # Connect vision toolkit to the microscope
    vision_toolkit.connect(sem)

    # Add databar to the image without a label
    img_with_databar = vision_toolkit.add_databar(image, databar_config)
    img_with_databar.save(tif_path)
    logger.info(f'[{prefix}] Grab sem frame done.')

    # Add databar to the image with a label
    # img_with_labeled_databar = vision_toolkit.add_databar(image, databar_config, "SZ lab")
    # img_with_labeled_databar.save(rf"{save_dir}/{prefix}_labeled.tif")


def sem_stage_actual(sem: SdbMicroscopeClient, logger: Logger, x_mm: float, y_mm: float):
    position = StagePosition(x=x_mm/1000, y=y_mm/1000)
    sem.specimen.stage.absolute_move(position)
    logger.info(f"Stage absolute move to x={x_mm},y={y_mm}(mm)")


def sem_stage_relative(sem: SdbMicroscopeClient, logger: Logger, interval: float, x_cnt: int, y_cnt: int):
    delta_position = StagePosition(x=x_cnt*interval, y=y_cnt*interval)
    sem.specimen.stage.relative_move(delta_position)
    if x_cnt:
        logger.info(f"Stage {'right' if x_cnt > 0 else 'left'} move {x_cnt}*{interval}mm")
    if y_cnt:
        logger.info(f"Stage {'up' if y_cnt > 0 else 'down'} move {y_cnt}*{interval}mm")


def sem_eds_detector(sem: SdbMicroscopeClient, logger: Logger, position: str):
    if 'insert' in position.lower():
        insert_settings = DetectorInsertSettings(type=DetectorType.EDS, insert_position=position)
        sem.detector.insert(insert_settings)
        logger.info(f'Insert EDS detector to {position}')
    else:
        settings = DetectorRetractSettings(type=DetectorType.EDS)
        sem.detector.retract(settings)
        logger.info(f'Retract EDS detector')


def is_tcp_phase(composition_result: List[ChemicalCompositionEntry], phase_statis_result: EdsPhaseStatisticsEntry, logger: Logger, index: int):
    if phase_statis_result.area_in_percent > 5:
        return False
    judge_rule = {
        'Nickel': {'compare': '<', 'value': 40},
        'Tungsten': {'compare': '>', 'value': 20}
    }
    match_cnt = 0
    for compose_item in composition_result:
        if compose_item.element.name in judge_rule.keys():
            if judge_rule[compose_item.element.name]['compare'] == '<':
                ele_ok = compose_item.weight_percentage < judge_rule[compose_item.element.name]['value']
            else:
                ele_ok = compose_item.weight_percentage > judge_rule[compose_item.element.name]['value']
            logger.info(f"In phase {index}: {compose_item.element.name} weight_percentage = {compose_item.weight_percentage}")
            if ele_ok:
                match_cnt += 1
                if match_cnt == len(judge_rule.keys()):
                    return True
    return False


def sem_eds_phase_map(sem: SdbMicroscopeClient,
                      resolution: tuple[int,int],
                      dwell: float,
                      frames_n: int,
                      component_n: int,
                      logger: Logger,
                      save_dir: str, prefix: str) -> 'tuple[Optional[List[ChemicalCompositionEntry]], Optional[EdsPhaseStatisticsEntry]]':
    sem_active_view(sem=sem, view_i=1, logger=logger)
    resolution_str = f"{resolution[0]}x{resolution[1]}"
    orig_dwell = sem.beams.electron_beam.scanning.dwell_time.value
    sem.beams.electron_beam.scanning.dwell_time.value = dwell
    acquisition_time = resolution[0] * resolution[1] * dwell * frames_n
    # region = Region(type=RegionType.FULL_FRAME)
    # spectrum = sem.analysis.eds.acquire_spectrum(region, acquisition_time)

    # Create a new empty EDS stream and activate it
    sem.analysis.eds.mapping.reset_stream()

    # Scan the entire field of view for acquisition_time seconds; the EDS stream will register X-rays generated by the scanning
    sem.imaging.start_acquisition()
    logger.info(f'[{prefix}] Start acquisition EDS data, will cost {acquisition_time:.1f}s...')
    time.sleep(acquisition_time)
    sem.imaging.stop_acquisition()
    logger.info(f'[{prefix}] Stop acquisition EDS data.')

    # Get the active stream and close it to enable data processing
    eds_stream = sem.analysis.eds.mapping.get_stream()
    eds_stream.close()

    logger.info(f'[{prefix}] Begin save EDS stream pad file...')
    eds_stream.save(rf'{save_dir}/{prefix}_eds_stream.pad')
    logger.info(f'[{prefix}] Save EDS stream pad file done.')

    # Analyze the stream for phases and prepare the mapping engine
    elements_found = [ChemicalElement('O'), ChemicalElement('Cr'), ChemicalElement('Co'),
                          ChemicalElement('Ni'), ChemicalElement('Al'), ChemicalElement('Si'),
                          ChemicalElement('Ta'), ChemicalElement('W'), ChemicalElement('Re'),
                          ChemicalElement('Mo')]
    find_tcp_phase = False
    for comp_i in range(component_n, component_n+3):
        logger.info(f'[{prefix}] Begin run EDS phase analysis(component_count={comp_i})...')
        settings = EdsPhaseAnalysisSettings(
            component_count=comp_i,
            segmentation_resolution=resolution_str if resolution_str in EdsSegmentationResolution.get_all_items() else EdsSegmentationResolution.PRESET_768X512,
            filter_type=EdsSegmentationFilterType.MEAN,
            filter_mask=EdsSegmentationFilterMask.PRESET_3X3,
        )
        result = eds_stream.run_phase_analysis(settings)
        logger.info(f'[{prefix}] End run EDS phase analysis(component_count={comp_i}).')
        for phase_index in result.get_all_phases():
            phase_spectrum = eds_stream.get_phase_spectrum(phase_index)
            # elements_found = eds_stream.get_peak_id()
            composition_result = sem.analysis.eds.get_composition(phase_spectrum, elements_found)
            phase_statis_result = result.statistics[phase_index - 1]
            if is_tcp_phase(composition_result=composition_result, phase_statis_result=phase_statis_result, logger=logger, index=phase_index):
                logger.info(f"[{prefix}] use component_count={comp_i} find TCP phase(index={phase_index}), area={phase_statis_result.area_in_percent}")
                map_image = eds_stream.get_phase_map([phase_index])
                map_image.save(rf"{save_dir}/{prefix}_phase_{phase_index}_map.tif")
                find_tcp_phase = True
                break
        if find_tcp_phase:
            break
    # Generate phase maps and save them to disk along with corresponding phase spectra in EMSA format
    all_map_image = eds_stream.get_phase_map(result.get_all_phases())
    all_map_image.save(rf"{save_dir}/{prefix}_phase_all_map.tif")
    if find_tcp_phase:
        logger.info(f"[{prefix}] Current EDS phase analysis done")
    else:
        composition_result = None
        phase_statis_result = None
        logger.warning(f"[{prefix}] Current EDS phase analysis not found TCP phase")

    # Free all server-side resources associated with the EDS stream
    # eds_stream.dispose()
    sem.beams.electron_beam.scanning.dwell_time.value = orig_dwell
    return composition_result, phase_statis_result


def tk_show(df: pd.DataFrame, title: str, geometry: str = "700x300"):
    root = tk.Tk()
    root.title(title)
    root.geometry(geometry)

    # 创建表格框架
    frame = ttk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    # 添加滚动条
    scrollbar_y = ttk.Scrollbar(frame)
    scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

    scrollbar_x = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
    scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

    # 创建Treeview
    columns = list(df.columns)
    tree = ttk.Treeview(frame, columns=columns, show='headings',
                        yscrollcommand=scrollbar_y.set,
                        xscrollcommand=scrollbar_x.set)

    # 设置列标题
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=100)

    # 添加数据
    for _, row in df.iterrows():
        tree.insert('', 'end', values=list(row))

    # 配置滚动条
    scrollbar_y.config(command=tree.yview)
    scrollbar_x.config(command=tree.xview)

    tree.pack(fill=tk.BOTH, expand=True)
    root.mainloop()


def sem_statis_eds_composition(composition_result_list: list[List[ChemicalCompositionEntry]], logger: Logger, show_statis=True, need_plot: bool = False, save_dir: str = './output/eds_statis'):
    all_composition_entry_statis = dict()
    processed_n = 0
    for each_composition_list in composition_result_list:
        curr_keys = list(all_composition_entry_statis.keys())
        for composition_entry in each_composition_list:
            if composition_entry.element.name not in all_composition_entry_statis:
                all_composition_entry_statis[composition_entry.element.name] = {
                    'atomic_percentage': [0]*processed_n + [composition_entry.atomic_percentage],
                    'weight_percentage': [0]*processed_n + [composition_entry.weight_percentage],
                    'net_counts_element': [0]*processed_n + [composition_entry.net_counts_element],
                }
            else:
                all_composition_entry_statis[composition_entry.element.name]['atomic_percentage'].append(composition_entry.atomic_percentage)
                all_composition_entry_statis[composition_entry.element.name]['weight_percentage'].append(composition_entry.weight_percentage)
                all_composition_entry_statis[composition_entry.element.name]['net_counts_element'].append(composition_entry.net_counts_element)
                curr_keys.remove(composition_entry.element.name)
        for miss_element in curr_keys:
            all_composition_entry_statis[miss_element]['atomic_percentage'].append(0)
            all_composition_entry_statis[miss_element]['weight_percentage'].append(0)
            all_composition_entry_statis[miss_element]['net_counts_element'].append(0)
        processed_n += 1
    for ele, val in all_composition_entry_statis.items():
        assert processed_n == len(val['atomic_percentage'])

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 统计all_composition_entry_statis中每个element的atomic_percentage、weight_percentage和net_counts_element统计分布
    summary_rows = []
    for metric_name in ['atomic_percentage', 'weight_percentage']:
        for ele, val in all_composition_entry_statis.items():
            metric_values = np.array(val[metric_name])
            summary_rows.append({
                "element": ele,
                "metric": metric_name,
                "mean": np.round(np.mean(metric_values), decimals=3),
                "std": np.round(np.std(metric_values), decimals=3),
                "min": np.round(np.min(metric_values), decimals=3),
                "max": np.round(np.max(metric_values), decimals=3),
                "median": np.round(np.median(metric_values), decimals=3),
            })
    summary_df = pd.DataFrame(summary_rows)
    if show_statis:
        tk_show(summary_df, '所有子区域中TCP相的化学成分统计分布', "1000x600")
    # 保存Excel
    excel_path = save_dir / "eds_composition_statistics.xlsx"
    if excel_path.exists() and excel_path.is_file():
        if show_statis:
            pyautogui.alert(
                text=f"Please ensure eds_composition_statistics.xlsx is not open",
                title="Close file",
                button="确定"
            )
        excel_path.unlink()
    with pd.ExcelWriter(excel_path) as writer:
        summary_df.to_excel(
            writer,
            sheet_name="summary",
            index=False
        )
        # 保存原始数据
        for ele, val in all_composition_entry_statis.items():
            pd.DataFrame(val).to_excel(
                writer,
                sheet_name=ele[:31],
                index=False
            )
    logger.info(f"EDS chemistry composition excel saved to: {excel_path}")
    # 如果need_plot为true，那么还需要使用matplotlib将统计结果图示
    # pyautogui.alert(
    #     text=f"{summary_df.to_string(index=False)}",
    #     title="化学元素统计结果",
    #     button="确定"
    # )
    logger.info(f'EDS chemistry composition statistic:\n{summary_df}')
    if need_plot:
        for ele, val in all_composition_entry_statis.items():
            for metric_name, metric_values in val.items():
                plt.figure(figsize=(8, 4))
                plt.plot(metric_values)
                plt.title(f"{ele} - {metric_name}")
                plt.xlabel("Measurement Index")
                plt.ylabel(metric_name)
                plt.grid(True)
                plt.tight_layout()
                fig_path = (
                    save_dir /
                    f"{ele}_{metric_name}.png"
                )
                plt.savefig(fig_path)
                plt.close()

    return summary_df

def sem_statis_eds_phase(phase_statis_result_list: list[EdsPhaseStatisticsEntry], logger: Logger, show_statis=True, need_plot: bool = False, save_dir: str = './output/eds_statis'):
    percent_list = []
    area_um2_list = []
    area_pixel_list = []
    for phase_statis_entry in phase_statis_result_list:
        percent_list.append(phase_statis_entry.area_in_percent)
        area_um2_list.append(phase_statis_entry.area_in_meters * 1000 * 1000 * 1000 * 1000)
        area_pixel_list.append(phase_statis_entry.area_in_pixels)
    phase_statis_all = {
        "Area(um2)": np.array(area_um2_list),
        "Area(px)": np.array(area_pixel_list),
        "Area(%)": np.array(percent_list),
    }
    summary_rows = []
    for metric_name, metric_values in phase_statis_all.items():
        summary_rows.append({
            "metric": metric_name,
            "mean": np.round(np.mean(metric_values), decimals=3),
            "std": np.round(np.std(metric_values), decimals=3),
            "min": np.round(np.min(metric_values), decimals=3),
            "max": np.round(np.max(metric_values), decimals=3),
            "median": np.round(np.median(metric_values), decimals=3),
        })
    summary_df = pd.DataFrame(summary_rows)
    if show_statis:
        tk_show(summary_df, '所有子区域中TCP相的面积统计分布', "700x300")
    # 保存Excel
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    excel_path = save_dir / "eds_phase_area.xlsx"
    if excel_path.exists() and excel_path.is_file():
        if show_statis:
            pyautogui.alert(
                text=f"Please ensure eds_phase_area.xlsx is not open",
                title="Close file",
                button="确定"
            )
        excel_path.unlink()
    with pd.ExcelWriter(excel_path) as writer:
        summary_df.to_excel(
            writer,
            sheet_name="summary",
            index=False
        )
        # 保存原始数据
        pd.DataFrame(phase_statis_all).to_excel(
            writer,
            sheet_name="detail",
            index=False
        )
    logger.info(f"EDS phase area excel saved to: {excel_path}")
    # 如果need_plot为true，那么还需要使用matplotlib将统计结果图示
    # pyautogui.alert(
    #     text=f"{summary_df.to_string(index=False)}",
    #     title="相面积占比",
    #     button="确定"
    # )
    logger.info(f'EDS phase area statistic:\n{summary_df}')
    if need_plot:
        for metric_name, metric_values in phase_statis_all.items():
            plt.figure(figsize=(8, 4))
            plt.plot(metric_values)
            plt.title(f"{metric_name}")
            plt.xlabel("Measurement Index")
            plt.ylabel(metric_name)
            plt.grid(True)
            plt.tight_layout()
            fig_path = (
                save_dir /
                f"{metric_name}.png"
            )
            plt.savefig(fig_path)
            plt.close()

    return summary_df
