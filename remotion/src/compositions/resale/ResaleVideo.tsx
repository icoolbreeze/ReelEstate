import React from "react";
import { BaseLayout } from "../../shared/BaseLayout";
import { areaText, locationText, priceText } from "../../shared/format";
import { ACCENTS } from "../../shared/theme";
import type { Project } from "../../types";

/** 二手房：挂牌价（截至日期）+ 房源核验编码 常驻显示。 */
export const ResaleVideo: React.FC<Project> = (project) => (
  <BaseLayout
    project={project}
    accent={ACCENTS.resale}
    fields={[
      { label: "类型", value: project.property.property_type },
      { label: "面积", value: areaText(project) },
      { label: "位置", value: locationText(project) },
      { label: "价格", value: priceText(project) },
      { label: "核验编码", value: project.resale?.verification_code ?? "" },
      { label: "机构", value: project.agency.full_name },
    ]}
  />
);
