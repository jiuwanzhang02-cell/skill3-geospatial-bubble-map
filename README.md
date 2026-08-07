1.Skill 定位
`plot-geospatial-bubble-map` 是一个用于绘制地理气泡散点图的 Codex Skill。它根据数据中的经纬度确定圆圈位置，用一个变量控制圆圈大小，并可用另一个变量控制圆圈颜色，适合制作全球或区域的数据分布图。

该 Skill 主要用于站点观测、事件频率、海拔、人口、排放、灾害、气候指标和遥感数据等空间分布展示。输出可用于论文、报告和演示文稿。

2.适用数据
Skill 支持 CSV、TXT、TSV、Excel、NetCDF、Zarr、GeoTIFF、HDF5、HDF-EOS 和 GRIB 等格式。

对于 CSV 等表格数据，每一行代表一个空间点。数据至少需要包含经度、纬度和控制圆圈大小的变量。若需要颜色编码，还应提供一个颜色变量。常见结构是 `lon、lat、size、T`，其中 lon 和 lat 表示位置，size 控制圆圈大小，T 控制颜色。

对于 NetCDF、Zarr、GRIB 或 HDF 数据，经纬度可以是一维规则坐标，也可以是与科学变量形状一致的二维坐标。如果数据还包含时间、高度或模式成员等维度，需要明确选择某个切片，或指定平均、求和、最大值等处理方式。

GeoTIFF 会使用像元中心作为圆圈位置。地理坐标系数据可以直接绘制；投影坐标数据需要先转换到经纬度坐标。

经度可以使用 −180–180 或 0–360。0–360 数据会自动转换为 −180–180。无效坐标和缺失值会被排除。大小变量默认不能为负数。

3.调用方式
在 Codex 中可以直接指定 Skill，例如：

“使用 `$plot-geospatial-bubble-map` 读取这个 CSV，根据 lon 和 lat 绘制矩形全球地图，size 控制圆圈大小并分成 5 级，T 控制颜色并使用 RdBu，添加陆地、海岸线和国界，输出 300 DPI PNG。”

4.示例展示
随机生成了一个数据绘制的图片示例：

<img width="4325" height="2053" alt="image" src="https://github.com/user-attachments/assets/75020432-1ab6-44ca-8171-0a73bab9ba14" />

给予了lon,lat,size,T四个变量，其中size控制圆圈大小，T生成圆圈的颜色。
