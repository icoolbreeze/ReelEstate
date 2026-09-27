import React from "react";
import { BaseLayout } from "../../shared/BaseLayout";
import { areaText, locationText, priceText } from "../../shared/format";
import { ACCENTS } from "../../shared/theme";
import type { Project } from "../../types";

/** 租赁：月租金 + 押付方式 + 整租/合租 常驻显示。 */
export const RentalVideo: React.FC<Project> = (project) => (
  <BaseLayout
    project={project}
    accent={ACCENTS.rental}
    fields={[
      { label: "租赁", value: [project.rental?.rent_type, project.property.property_type].filter(Boolean).join("·") },
      { label: "面积", value: areaText(project) },
      { label: "位置", value: locationText(project) },
      { label: "租金", value: priceText(project) },
      { label: "押付", value: project.rental?.payment_terms ?? "" },
      { label: "机构", value: project.agency.full_name },
    ]}
  />
);
