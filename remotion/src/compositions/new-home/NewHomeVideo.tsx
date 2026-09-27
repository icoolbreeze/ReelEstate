import React from "react";
import { BaseLayout } from "../../shared/BaseLayout";
import { areaText, locationText, priceText } from "../../shared/format";
import { ACCENTS } from "../../shared/theme";
import type { Project } from "../../types";

/** 新房：开发商全称 + 预售/销售许可证号 常驻显示（房地产广告发布规定第7条）。 */
export const NewHomeVideo: React.FC<Project> = (project) => (
  <BaseLayout
    project={project}
    accent={ACCENTS["new-home"]}
    fields={[
      { label: "项目", value: project.new_home?.project_name ?? "" },
      { label: "类型", value: project.property.property_type },
      { label: "面积", value: areaText(project) },
      { label: "位置", value: locationText(project) },
      { label: "价格", value: priceText(project) },
      { label: "开发商", value: project.new_home?.developer_full_name ?? "" },
      { label: "预售证", value: project.new_home?.presale_permit_no ?? "" },
      { label: "代理", value: project.agency.full_name },
    ]}
  />
);
