/**
 * Data Analysis Toggle component for the application
 * user can toggle between Master EDI and CHS EDI data
 * Master EDI data is the default data
 * CHS EDI data is the data that is used for the CHS department
 * 
 * 
 * */

import React from "react";

export default function DataAnalysisToggle({ value, onChange }) {
  return (
    <div className="flex items-center gap-4">
      <label className="flex items-center cursor-pointer">
        <input
          type="radio"
          className="peer hidden"
          name="data-analysis-toggle"
          value="master"
          checked={value === "master"}
          onChange={() => onChange("master")}
        />
        <span
          className={`px-4 py-2 rounded-l-md border border-gray-300 text-sm font-medium transition-colors 
            ${
              value === "master"
                ? "bg-[#3b82f6] text-white border-[#3b82f6]"
                : "bg-white text-gray-700 hover:bg-gray-50"
            }`}
        >
          Primary EDI
        </span>
      </label>
      <label className="flex items-center cursor-pointer">
        <input
          type="radio"
          className="peer hidden"
          name="data-analysis-toggle"
          value="chs"
          checked={value === "chs"}
          onChange={() => onChange("chs")}
        />
        <span
          className={`px-4 py-2 rounded-r-md border border-gray-300 text-sm font-medium transition-colors 
            ${
              value === "chs"
                ? "bg-[#3b82f6] text-white border-[#3b82f6]"
                : "bg-white text-gray-700 hover:bg-gray-50"
            }`}
        >
          CHS EDI
        </span>
      </label>
    </div>
  );
}
