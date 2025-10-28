import React, { useState, useEffect } from "react";
import {curateAnnotation, editAnnotation, curateClassification, editClassification} from "@/app/lib/service";
import {Annotation, QuantitativeStatement, TextSpan} from "@/app/lib/prepare_annotated_text";

const CheckedLabel = ({
                        annotation_type,
                        index,
                        visible,
                      }: {
  annotation_type: string;
  index: number;
  visible: boolean;
}) => {
  let display: string = "hidden"
  if (visible) {
    display = "inline-flex"
  }
  return (
    <span id={"checked-label-".concat(annotation_type) + index}
          className={display.concat(" items-center justify-center bg-green-100 text-green-800 text-xs font-normal ms-1.5 me-0.5 pl-2 pr-2.5 py-0.5 rounded-full dark:bg-green-900 dark:text-green-300")}>
      <svg className="w-2.5 h-2.5 mt-px mr-1" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none"
           viewBox="0 0 16 12">
        <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M1 5.917 5.724 10.5 15 1.5"/>
      </svg>
      <span>checked</span>
    </span>
  )
}

const RejectedLabel = ({
                         annotation_type,
                         index,
                         visible,
                       }: {
  annotation_type: string;
  index: number;
  visible: boolean;
}) => {
  let display: string = "hidden"
  if (visible) {
    display = "inline-flex"
  }
  return (
    <span id={"rejected-label-".concat(annotation_type) + index}
          className={display.concat(" items-center justify-center bg-red-100 text-red-800 text-xs font-normal ms-1.5 me-0.5 pl-1.5 pr-2.5 py-0.5 rounded-full dark:bg-red-900 dark:text-red-300")}>
      <svg className="w-4 h-3.5 mt-px mr-0.5" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none"
           viewBox="0 0 23 23">
        <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M6 18 17.94 6M18 18 6.06 6"/>
      </svg>
      <span>rejected</span>
    </span>
  )
}

const CommentLabel = ({
                        annotation_type,
                        index,
                        visible,
                        comment,
                      }: {
  annotation_type: string;
  index: number;
  visible: boolean;
  comment: string;
}) => {
  let display: string = "hidden"
  if (visible) {
    display = "inline-flex"
  }
  return (
    <span id={"comment-label-".concat(annotation_type) + index}
          className={display.concat(" items-center justify-center bg-amber-100 text-amber-800 text-xs font-normal me-0.5 px-2 py-0.5 rounded-full dark:bg-amber-900 dark:text-amber-300")}>
      <svg className="w-3.5 h-3.5 mb-px mr-1" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none"
           viewBox="0 0 21 21">
        <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M7 9h5m3 0h2M7 12h2m3 0h5M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-6.616a1 1 0 0 0-.67.257l-2.88 2.592A.5.5 0 0 1 8 18.477V17a1 1 0 0 0-1-1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"/>
      </svg>
      <span>{comment}</span>
    </span>
  )
}

const hideForms = (annotation_type: string, index: number) => {
  let approve_form = document.getElementById("approve-".concat(annotation_type) + index);
  let reject_form = document.getElementById("reject-".concat(annotation_type) + index);
  let edit_form = document.getElementById("edit-".concat(annotation_type) + index);
  if (approve_form) {
    approve_form.style.display = 'none';
  }
  if (reject_form) {
    reject_form.style.display = 'none';
  }
  if (edit_form) {
    edit_form.style.display = 'none';
  }
}

const hideLabels = (annotation_type: string, index: number) => {
  let checked_label = document.getElementById("checked-label-".concat(annotation_type) + index);
  let rejected_label = document.getElementById("rejected-label-".concat(annotation_type) + index);
  let comment_label = document.getElementById("comment-label-".concat(annotation_type) + index);
  if (checked_label) {
    checked_label.style.display = 'none';
  }
  if (rejected_label) {
    rejected_label.style.display = 'none';
  }
  if (comment_label) {
    comment_label.style.display = 'none';
  }
}

const displayInlineFlex = (element_id: string) => {
  const html_element = document.getElementById(element_id);
  if (html_element) {
    html_element.style.display = "inline-flex";
  }
}

const AnnotationCuration = async (analysis_name: string, paper_id: string, index: number, annotation_type: string, annotation_text: string, approved: boolean, comment: string) => {
  const response = await curateAnnotation(analysis_name, paper_id, index, annotation_type, annotation_text, approved, comment);

  // Successfully curated?
  if (response.includes("success")) {
    // Update labels of annotation and hide form
    hideForms(annotation_type, index);

    const decision_buttons = document.getElementById("decision-buttons-".concat(annotation_type) + index);
    if (decision_buttons) {
      decision_buttons.style.marginTop = "auto";
    }

    const annotation_labels = document.getElementById("labels-".concat(annotation_type) + index);
    if (annotation_labels) {
      annotation_labels.style.display = "flex";
      hideLabels(annotation_type, index);
      if (approved) {
        displayInlineFlex("checked-label-".concat(annotation_type) + index);
      } else {
        displayInlineFlex("rejected-label-".concat(annotation_type) + index);
      }
      if (comment) {
        const comment_label = document.getElementById("comment-label-".concat(annotation_type) + index);
        if (comment_label) {
          comment_label.children[1].innerHTML = comment;
          comment_label.style.display = "inline-flex";
        }
      }
    }
  } else {
    // if not successfully curated, alert user
    alert(response)
  }
}

const ClassificationCuration = async (analysis_name: string, paper_id: string, index: number, quantity_text: string, classification_type: string, approved: boolean, comment: string) => {
  const response = await curateClassification(analysis_name, paper_id, index, quantity_text, classification_type, approved, comment);

  // Successfully curated?
  if (response.includes("success")) {
    // Update labels of annotation and hide form
    hideForms(classification_type, index);

    const decision_buttons = document.getElementById("decision-buttons-".concat(classification_type) + index);
    if (decision_buttons) {
      decision_buttons.style.marginTop = "auto";
    }

    const annotation_labels = document.getElementById("labels-".concat(classification_type) + index);
    if (annotation_labels) {
      annotation_labels.style.display = "flex";
      hideLabels(classification_type, index);
      if (approved) {
        displayInlineFlex("checked-label-".concat(classification_type) + index);
      } else {
        displayInlineFlex("rejected-label-".concat(classification_type) + index);
      }
      if (comment) {
        const comment_label = document.getElementById("comment-label-".concat(classification_type) + index);
        if (comment_label) {
          comment_label.children[1].innerHTML = comment;
          comment_label.style.display = "inline-flex";
        }
      }
    }
  } else {
    // if not successfully curated, alert user
    alert(response)
  }
}

const SubmitCurateForm = async (analysis_name: string, paper_id: string, index: number, annotation_type: string, annotation_text: string, approved: boolean, e: React.SyntheticEvent) => {
  // Prevent the browser from reloading the page
  e.preventDefault();

  // API request
  const target = e.target as typeof e.target & {
    comment: { value: string };
  };
  await AnnotationCuration(analysis_name, paper_id, index, annotation_type, annotation_text, approved, target.comment.value);
}

const SubmitCurateClassificationForm = async (analysis_name: string, paper_id: string, index: number, classification_type: string, quantity_text: string, approved: boolean, e: React.SyntheticEvent) => {
  // Prevent the browser from reloading the page
  e.preventDefault();

  // API request
  const target = e.target as typeof e.target & {
    comment: { value: string };
  };
  await ClassificationCuration(analysis_name, paper_id, index, quantity_text, classification_type, approved, target.comment.value);
}

const RejectClassificationForm = ({
                                    analysis_name,
                                    paper_id,
                                    classification_type,
                                    quantity_text,
                                    index,
                                  }: {
  analysis_name: string;
  paper_id: string;
  classification_type: string;
  quantity_text: string;
  index: number;
}) => (
  <form method="put"
        onSubmit={(e: React.SyntheticEvent) => SubmitCurateClassificationForm(analysis_name, paper_id, index, classification_type, quantity_text, false, e)}
        id={"reject-".concat(classification_type) + index} className="max-w-sm mt-1 mx-auto hidden">
    <div className="relative mr-1.5 mb-auto">
      <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
             xmlns="http://www.w3.org/2000/svg" fill="currentColor"
             viewBox="0 0 24 24">
          <path fillRule="evenodd"
                d="M3.559 4.544c.355-.35.834-.544 1.33-.544H19.11c.496 0 .975.194 1.33.544.356.35.559.829.559 1.331v9.25c0 .502-.203.981-.559 1.331-.355.35-.834.544-1.33.544H15.5l-2.7 3.6a1 1 0 0 1-1.6 0L8.5 17H4.889c-.496 0-.975-.194-1.33-.544A1.868 1.868 0 0 1 3 15.125v-9.25c0-.502.203-.981.559-1.331ZM7.556 7.5a1 1 0 1 0 0 2h8a1 1 0 0 0 0-2h-8Zm0 3.5a1 1 0 1 0 0 2H12a1 1 0 1 0 0-2H7.556Z"
                clipRule="evenodd"/>
        </svg>
      </div>
      <input type="text" id="comment"
             className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-red-100 focus:border-red-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-red-500 dark:focus:border-red-500"
             placeholder="Comment (optional)"/>
    </div>
    <button type="submit"
            className="px-3 py-2 text-xs font-medium text-center text-white bg-red-500 hover:bg-red-600 focus:ring-4 focus:outline-none focus:ring-red-100 rounded-lg dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800">
      Reject
    </button>
  </form>
)

const ApproveClassificationForm = ({
                                     analysis_name,
                                     paper_id,
                                     classification_type,
                                     quantity_text,
                                     index,
                                   }: {
  analysis_name: string;
  paper_id: string;
  classification_type: string;
  quantity_text: string;
  index: number;
}) => (
  <form method="put"
        onSubmit={(e: React.SyntheticEvent) => SubmitCurateClassificationForm(analysis_name, paper_id, index, classification_type, quantity_text, true, e)}
        id={"approve-".concat(classification_type) + index} className="max-w-sm mt-1 mx-auto hidden">
    <div className="relative mr-1.5 mb-auto">
      <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
             xmlns="http://www.w3.org/2000/svg" fill="currentColor"
             viewBox="0 0 24 24">
          <path fillRule="evenodd"
                d="M3.559 4.544c.355-.35.834-.544 1.33-.544H19.11c.496 0 .975.194 1.33.544.356.35.559.829.559 1.331v9.25c0 .502-.203.981-.559 1.331-.355.35-.834.544-1.33.544H15.5l-2.7 3.6a1 1 0 0 1-1.6 0L8.5 17H4.889c-.496 0-.975-.194-1.33-.544A1.868 1.868 0 0 1 3 15.125v-9.25c0-.502.203-.981.559-1.331ZM7.556 7.5a1 1 0 1 0 0 2h8a1 1 0 0 0 0-2h-8Zm0 3.5a1 1 0 1 0 0 2H12a1 1 0 1 0 0-2H7.556Z"
                clipRule="evenodd"/>
        </svg>
      </div>
      <input type="text" id="comment"
             className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-green-100 focus:border-green-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-green-500 dark:focus:border-green-500"
             placeholder="Comment (optional)"/>
    </div>
    <button type="submit"
            className="px-3 py-2 text-xs font-medium text-center text-white bg-green-500 hover:bg-green-600 focus:ring-4 focus:outline-none focus:ring-green-100 rounded-lg dark:bg-green-600 dark:hover:bg-green-700 dark:focus:ring-green-800">
      Approve
    </button>
  </form>
)

const RejectForm = ({
                      analysis_name,
                      paper_id,
                      annotation_type,
                      annotation_text,
                      index,
                    }: {
  analysis_name: string;
  paper_id: string;
  annotation_type: string;
  annotation_text: string;
  index: number;
}) => (
  <form method="put"
        onSubmit={(e: React.SyntheticEvent) => SubmitCurateForm(analysis_name, paper_id, index, annotation_type, annotation_text, false, e)}
        id={"reject-".concat(annotation_type) + index} className="max-w-sm mt-1 mx-auto hidden">
    <div className="relative mr-1.5 mb-auto">
      <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
             xmlns="http://www.w3.org/2000/svg" fill="currentColor"
             viewBox="0 0 24 24">
          <path fillRule="evenodd"
                d="M3.559 4.544c.355-.35.834-.544 1.33-.544H19.11c.496 0 .975.194 1.33.544.356.35.559.829.559 1.331v9.25c0 .502-.203.981-.559 1.331-.355.35-.834.544-1.33.544H15.5l-2.7 3.6a1 1 0 0 1-1.6 0L8.5 17H4.889c-.496 0-.975-.194-1.33-.544A1.868 1.868 0 0 1 3 15.125v-9.25c0-.502.203-.981.559-1.331ZM7.556 7.5a1 1 0 1 0 0 2h8a1 1 0 0 0 0-2h-8Zm0 3.5a1 1 0 1 0 0 2H12a1 1 0 1 0 0-2H7.556Z"
                clipRule="evenodd"/>
        </svg>
      </div>
      <input type="text" id="comment"
             className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-red-100 focus:border-red-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-red-500 dark:focus:border-red-500"
             placeholder="Comment (optional)"/>
    </div>
    <button type="submit"
            className="px-3 py-2 text-xs font-medium text-center text-white bg-red-500 hover:bg-red-600 focus:ring-4 focus:outline-none focus:ring-red-100 rounded-lg dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800">
      Reject
    </button>
  </form>
)

const ApproveForm = ({
                       analysis_name,
                       paper_id,
                       annotation_type,
                       annotation_text,
                       index,
                     }: {
  analysis_name: string;
  paper_id: string;
  annotation_type: string;
  annotation_text: string;
  index: number;
}) => (
  <form method="put"
        onSubmit={(e: React.SyntheticEvent) => SubmitCurateForm(analysis_name, paper_id, index, annotation_type, annotation_text, true, e)}
        id={"approve-".concat(annotation_type) + index} className="max-w-sm mt-1 mx-auto hidden">
    <div className="relative mr-1.5 mb-auto">
      <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
             xmlns="http://www.w3.org/2000/svg" fill="currentColor"
             viewBox="0 0 24 24">
          <path fillRule="evenodd"
                d="M3.559 4.544c.355-.35.834-.544 1.33-.544H19.11c.496 0 .975.194 1.33.544.356.35.559.829.559 1.331v9.25c0 .502-.203.981-.559 1.331-.355.35-.834.544-1.33.544H15.5l-2.7 3.6a1 1 0 0 1-1.6 0L8.5 17H4.889c-.496 0-.975-.194-1.33-.544A1.868 1.868 0 0 1 3 15.125v-9.25c0-.502.203-.981.559-1.331ZM7.556 7.5a1 1 0 1 0 0 2h8a1 1 0 0 0 0-2h-8Zm0 3.5a1 1 0 1 0 0 2H12a1 1 0 1 0 0-2H7.556Z"
                clipRule="evenodd"/>
        </svg>
      </div>
      <input type="text" id="comment"
             className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-green-100 focus:border-green-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-green-500 dark:focus:border-green-500"
             placeholder="Comment (optional)"/>
    </div>
    <button type="submit"
            className="px-3 py-2 text-xs font-medium text-center text-white bg-green-500 hover:bg-green-600 focus:ring-4 focus:outline-none focus:ring-green-100 rounded-lg dark:bg-green-600 dark:hover:bg-green-700 dark:focus:ring-green-800">
      Approve
    </button>
  </form>
)

const SubmitEditForm = async (analysis_name: string, paper_id: string, index: number, annotation_type: string, current_annotation_text: string, e: React.SyntheticEvent) => {
  // Prevent the browser from reloading the page
  e.preventDefault();

  // API request
  const target = e.target as typeof e.target & {
    text: { value: string };
  };
  const text = target.text.value;
  const response = await editAnnotation(analysis_name, paper_id, index, annotation_type, current_annotation_text, text);

  // Successfully updated?
  if (response.includes("success")) {
    // Update annotation text and approve annotation
    const annotation_text = document.getElementById("annotation-text-".concat(annotation_type) + index);
    if (annotation_text) {
      annotation_text.innerText = text;
    }
    await AnnotationCuration(analysis_name, paper_id, index, annotation_type, text, true, "");
  } else {
    // if not successfully updated, alert user
    alert(response)
  }
}

const SubmitEditClassificationForm = async (analysis_name: string, paper_id: string, index: number, classification_type: string, quantity_text: string, e: React.SyntheticEvent) => {
  // Prevent the browser from reloading the page
  e.preventDefault();

  // API request
  const target = e.target as typeof e.target & {
    text: { value: string };
  };
  const classification_option = target.text.value;
  const response = await editClassification(analysis_name, paper_id, index, quantity_text, classification_type, classification_option);

  // Successfully updated?
  if (response.includes("success")) {
    // Update annotation text and approve annotation
    const annotation_text = document.getElementById("annotation-text-".concat(classification_type) + index);
    if (annotation_text) {
      annotation_text.innerText = classification_option;
    }
    await ClassificationCuration(analysis_name, paper_id, index, quantity_text, classification_type, true, "");
  } else {
    // if not successfully updated, alert user
    alert(response)
  }
}

const EditClassificationForm = ({
                                  analysis_name,
                                  paper_id,
                                  classification_type,
                                  quantity_text,
                                  index,
                                }: {
  analysis_name: string;
  paper_id: string;
  classification_type: string;
  quantity_text: string;
  index: number;
}) => {
  let options: string[] = [];
  if (classification_type === "statement_type") {
    options = ["assumption", "feasibility_estimation", "goal", "observation", "prediction", "requirement", "specification"];
  } else if (classification_type === "statement_rational") {
    options = ["arbitrary", "company_reported", "experiments", "expert_elicitation", "individual_literature_sources", "literature_review", "regression", "simulation_or_calculation", "rough_estimate_or_analogy"];
  } else if (classification_type === "statement_system") {
    options = ["real_world", "lab_or_prototype_or_pilot_system", "model"];
  }
  return (
    <form method="put"
          onSubmit={(e: React.SyntheticEvent) => SubmitEditClassificationForm(analysis_name, paper_id, index, classification_type, quantity_text, e)}
          id={"edit-".concat(classification_type) + index} className="max-w-sm mt-1 mx-auto hidden">
      <div className="relative mr-1.5 mb-auto">
        <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
          <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
               xmlns="http://www.w3.org/2000/svg" fill="none"
               viewBox="0 0 24 24">
            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                  d="m14.304 4.844 2.852 2.852M7 7H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4.5m2.409-9.91a2.017 2.017 0 0 1 0 2.853l-6.844 6.844L8 14l.713-3.565 6.844-6.844a2.015 2.015 0 0 1 2.852 0Z"/>
          </svg>
        </div>
        <select id="text"
                className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-amber-100 focus:border-amber-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-amber-400 dark:focus:border-amber-400"
                placeholder={"Choose correct ".concat(classification_type.replace("_", " "))}>
          {options.map((option, index) => (
            <option key={index}
                    value={option}>{option.charAt(0).toUpperCase() + option.slice(1).replace("_", " ")}</option>
          ))}
        </select>
      </div>
      <button type="submit"
              className="px-3 py-2 text-xs font-medium text-center text-white bg-amber-300 hover:bg-amber-400 focus:ring-4 focus:outline-none focus:ring-amber-100 rounded-lg dark:bg-amber-600 dark:hover:bg-amber-700 dark:focus:ring-amber-800">
        Save
      </button>
    </form>
  )
};

const EditForm = ({
                    analysis_name,
                    paper_id,
                    annotation_type,
                    annotation_text,
                    index,
                  }: {
  analysis_name: string;
  paper_id: string;
  annotation_type: string;
  annotation_text: string;
  index: number;
}) => (
  <form method="put"
        onSubmit={(e: React.SyntheticEvent) => SubmitEditForm(analysis_name, paper_id, index, annotation_type, annotation_text, e)}
        id={"edit-".concat(annotation_type) + index} className="max-w-sm mt-1 mx-auto hidden">
    <div className="relative mr-1.5 mb-auto">
      <div className="absolute inset-y-0 start-0 flex items-center ps-2.5 pointer-events-none">
        <svg className="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true"
             xmlns="http://www.w3.org/2000/svg" fill="none"
             viewBox="0 0 24 24">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="m14.304 4.844 2.852 2.852M7 7H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4.5m2.409-9.91a2.017 2.017 0 0 1 0 2.853l-6.844 6.844L8 14l.713-3.565 6.844-6.844a2.015 2.015 0 0 1 2.852 0Z"/>
        </svg>
      </div>
      <input type="text" id="text"
             className="block w-full bg-gray-50 border border-gray-300 text-gray-900 text-xs ps-8 rounded-lg focus:ring-amber-100 focus:border-amber-300 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-amber-400 dark:focus:border-amber-400"
             placeholder={"Corrected ".concat(annotation_type)}/>
    </div>
    <button type="submit"
            className="px-3 py-2 text-xs font-medium text-center text-white bg-amber-300 hover:bg-amber-400 focus:ring-4 focus:outline-none focus:ring-amber-100 rounded-lg dark:bg-amber-600 dark:hover:bg-amber-700 dark:focus:ring-amber-800">
      Save
    </button>
  </form>
)

const IconOnClick = (annotation_type: string, index: number, kind_of: string) => {
  hideForms(annotation_type, index);
  const form_to_show = document.getElementById(kind_of.concat("-", annotation_type) + index);
  const decision_buttons = document.getElementById("decision-buttons-".concat(annotation_type) + index);
  const labels = document.getElementById("labels-".concat(annotation_type) + index);
  if (form_to_show) {
    if (decision_buttons) {
      decision_buttons.style.marginTop = "0";
    }
    if (labels) {
      labels.style.display = 'none';
    }
    form_to_show.style.display = 'inline-flex';
  }
}

const DecisionButtons = ({
                           annotation_type,
                           index,
                         }: {
  annotation_type: string;
  index: number;
}) => (
  <div id={"decision-buttons-".concat(annotation_type) + index} className="inline-flex ml-auto my-auto">
    <button type="button" onClick={() => IconOnClick(annotation_type, index, "reject")}
            className="inline-flex items-center flex-shrink-0 w-8 h-8 text-red-500 bg-red-100 hover:bg-red-200 rounded-lg dark:bg-red-800 dark:text-red-200">
      <svg className="w-5 h-5 m-auto" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor"
           viewBox="0 0 20 20">
        <path
          d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 11.793a1 1 0 1 1-1.414 1.414L10 11.414l-2.293 2.293a1 1 0 0 1-1.414-1.414L8.586 10 6.293 7.707a1 1 0 0 1 1.414-1.414L10 8.586l2.293-2.293a1 1 0 0 1 1.414 1.414L11.414 10l2.293 2.293Z"/>
      </svg>
      <span className="sr-only">Reject icon</span>
    </button>
    <button type="button" onClick={() => IconOnClick(annotation_type, index, "edit")}
            className="inline-flex items-center mx-1 flex-shrink-0 w-8 h-8 text-yellow-500 bg-yellow-100 hover:bg-yellow-200 rounded-lg dark:bg-yellow-800 dark:text-yellow-200">
      <span
        className="inline-flex m-auto w-5 h-5 text-sm font-semibold text-yellow-100 bg-yellow-500 rounded-full dark:bg-yellow-200 dark:text-yellow-800">
        <svg className="w-3.5 h-3.5 m-auto" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none"
             viewBox="0 0 24 24">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M10.779 17.779 4.36 19.918 6.5 13.5m4.279 4.279 8.364-8.643a3.027 3.027 0 0 0-2.14-5.165 3.03 3.03 0 0 0-2.14.886L6.5 13.5m4.279 4.279L6.499 13.5m2.14 2.14 6.213-6.504M12.75 7.04 17 11.28"/>
        </svg>
      </span>
      <span className="sr-only">Edit icon</span>
    </button>
    <button type="button" onClick={() => IconOnClick(annotation_type, index, "approve")}
            className="inline-flex items-center flex-shrink-0 w-8 h-8 text-green-500 bg-green-100 hover:bg-green-200 rounded-lg dark:bg-green-800 dark:text-green-200">
      <svg className="w-5 h-5 m-auto" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor"
           viewBox="0 0 20 20">
        <path
          d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 8.207-4 4a1 1 0 0 1-1.414 0l-2-2a1 1 0 0 1 1.414-1.414L9 10.586l3.293-3.293a1 1 0 0 1 1.414 1.414Z"/>
      </svg>
      <span className="sr-only">Check icon</span>
    </button>
  </div>
)

const AnnotationElement = ({
                             analysis_name,
                             paper_id,
                             index,
                             type_shown,
                             type,
                             annotation,
                           }: {
  analysis_name: string;
  paper_id: string;
  index: number;
  type_shown: string;
  type: string;
  annotation: Annotation;
}) => (
  <li>
    <div className="flex rounded hover:bg-gray-100 dark:hover:bg-gray-600 p-2">
      <div className="my-auto">
        <div className="flex max-w-fit gap-1 items-start">
          <div
            className="w-20 ms-2 text-sm font-medium text-gray-900 rounded dark:text-gray-300">
            {type_shown}
          </div>
          <div className="my-auto">
            <div className="ms-2 me-2">
              <div id={"annotation-text-".concat(type) + index}
                   className="text-sm text-left text-balance font-normal text-gray-900 rounded dark:text-gray-300">
                {annotation.text}
              </div>
              <ApproveForm analysis_name={analysis_name} paper_id={paper_id} annotation_type={type} annotation_text={annotation.text}
                           index={index}></ApproveForm>
              <RejectForm analysis_name={analysis_name} paper_id={paper_id} annotation_type={type} annotation_text={annotation.text}
                          index={index}></RejectForm>
              <EditForm analysis_name={analysis_name} paper_id={paper_id} annotation_type={type} annotation_text={annotation.text}
                        index={index}></EditForm>
            </div>
            <span id={"labels-".concat(type) + index} className="flex mt-px items-end">
              {typeof annotation.approved === "undefined" ?
                <>
                  <CheckedLabel annotation_type={type} index={index} visible={false}></CheckedLabel>
                  <RejectedLabel annotation_type={type} index={index} visible={false}></RejectedLabel>
                </>
                :
                <>
                  <CheckedLabel annotation_type={type} index={index}
                                visible={annotation.approved}></CheckedLabel>
                  <RejectedLabel annotation_type={type} index={index}
                                 visible={!annotation.approved}></RejectedLabel>
                </>
              }
              {annotation.comment ?
                <CommentLabel annotation_type={type} index={index}
                              visible={true}
                              comment={annotation.comment}></CommentLabel>
                : <CommentLabel annotation_type={type} index={index} visible={false}
                                comment=""></CommentLabel>
              }
              </span>
          </div>
        </div>
      </div>
      <DecisionButtons annotation_type={type} index={index}></DecisionButtons>
    </div>
  </li>
)

const ClassificationElement = ({
                                 analysis_name,
                                 paper_id,
                                 index,
                                 type_shown,
                                 type,
                                 quantity_text,
                                 annotation,
                               }: {
  analysis_name: string;
  paper_id: string;
  index: number;
  type_shown: string;
  type: string;
  quantity_text: string;
  annotation: Annotation;
}) => (
  <li>
    <div className="flex rounded hover:bg-gray-100 dark:hover:bg-gray-600 p-2">
      <div className="my-auto">
        <div className="flex max-w-fit gap-1 items-start">
          <div
            className="w-20 ms-2 text-sm font-medium text-gray-900 rounded dark:text-gray-300">
            {type_shown}
          </div>
          <div className="my-auto">
            <div className="ms-2 me-2">
              <div id={"annotation-text-".concat(type) + index}
                   className="text-sm text-left text-balance font-normal text-gray-900 rounded dark:text-gray-300">
                {annotation.text}
              </div>
              <ApproveClassificationForm analysis_name={analysis_name} paper_id={paper_id} classification_type={type} quantity_text={quantity_text}
                                         index={index}></ApproveClassificationForm>
              <RejectClassificationForm analysis_name={analysis_name} paper_id={paper_id} classification_type={type} quantity_text={quantity_text}
                                        index={index}></RejectClassificationForm>
              <EditClassificationForm analysis_name={analysis_name} paper_id={paper_id} classification_type={type} quantity_text={quantity_text}
                                      index={index}></EditClassificationForm>
            </div>
            <span id={"labels-".concat(type) + index} className="flex mt-px items-end">
              {typeof annotation.approved === "undefined" ?
                <>
                  <CheckedLabel annotation_type={type} index={index} visible={false}></CheckedLabel>
                  <RejectedLabel annotation_type={type} index={index} visible={false}></RejectedLabel>
                </>
                :
                <>
                  <CheckedLabel annotation_type={type} index={index}
                                visible={annotation.approved}></CheckedLabel>
                  <RejectedLabel annotation_type={type} index={index}
                                 visible={!annotation.approved}></RejectedLabel>
                </>
              }
              {annotation.comment ?
                <CommentLabel annotation_type={type} index={index}
                              visible={true}
                              comment={annotation.comment}></CommentLabel>
                : <CommentLabel annotation_type={type} index={index} visible={false}
                                comment=""></CommentLabel>
              }
              </span>
          </div>
        </div>
      </div>
      <DecisionButtons annotation_type={type} index={index}></DecisionButtons>
    </div>
  </li>
)

const AnnotationTable = ({
                           analysis_name,
                           paper_id,
                           index,
                           quantitative_statement,
                         }: {
  analysis_name: string;
  paper_id: string;
  index: number;
  quantitative_statement: QuantitativeStatement;
}) => (
  <ul className="p-3 space-y-1 text-sm text-gray-700 dark:text-gray-200"
      aria-labelledby="dropdownDefaultButton">
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"entity"} type_shown={"Entity:"}
                       annotation={quantitative_statement.entity}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"property"} type_shown={"Property:"}
                       annotation={quantitative_statement.property}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"quantity"} type_shown={"Quantity:"}
                       annotation={quantitative_statement.quantity}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"temporal_scope"} type_shown={"Temporal scope:"}
                       annotation={quantitative_statement.temporal_scope}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"spatial_scope"} type_shown={"Spatial scope:"}
                       annotation={quantitative_statement.spatial_scope}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"reference"} type_shown={"Reference:"}
                       annotation={quantitative_statement.reference}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"method"} type_shown={"Method:"}
                       annotation={quantitative_statement.method}></AnnotationElement>
    <AnnotationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"qualifier"} type_shown={"Qualifier:"}
                       annotation={quantitative_statement.qualifier}></AnnotationElement>
    <ClassificationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"statement_type"} type_shown={"Type:"}
                           quantity_text={quantitative_statement.quantity.text}
                           annotation={quantitative_statement.type}></ClassificationElement>
    <ClassificationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"statement_rational"} type_shown={"Rational:"}
                           quantity_text={quantitative_statement.quantity.text}
                           annotation={quantitative_statement.rational}></ClassificationElement>
    <ClassificationElement analysis_name={analysis_name} paper_id={paper_id} index={index} type={"statement_system"} type_shown={"System:"}
                           quantity_text={quantitative_statement.quantity.text}
                           annotation={quantitative_statement.system}></ClassificationElement>
  </ul>
)
/*
  <li>
  <div className="flex rounded hover:bg-gray-100 dark:hover:bg-gray-600 p-2">
  <div className="my-auto">
  <div className="flex max-w-fit gap-1 items-start">
  <div
className="w-20 ms-2 text-sm font-medium text-gray-900 rounded dark:text-gray-300">
  Normalized quantity:
  </div>
<div className="my-auto">
  <div
    className="ms-2 me-2 text-sm mb-1 text-left text-balance font-normal text-gray-900 rounded dark:text-gray-300">
    {quantitative_statement.quantity_modifiers.map(modifier => modifier.text)}
  </div>
  <span className="items-end">
              {quantitative_statement.quantity_modifiers.length !== 0 && quantitative_statement.quantity_modifiers.every(x => x.approved === true) &&
                <CheckedLabel index={"defaultID"} visible={true}></CheckedLabel>
              }
    {quantitative_statement.quantity_modifiers.some(x => x.approved === false) &&
      <RejectedLabel index={"defaultID"} visible={true}></RejectedLabel>
    }
    {quantitative_statement.quantity_modifiers.filter(x => x.comment).length !== 0 &&
      <CommentLabel index={"defaultID"} visible={true}
                    comment={"" + quantitative_statement.quantity_modifiers.filter(x => x.comment).map(modifier => modifier.comment)}></CommentLabel>
    }
            </span>
</div>
</div>
</div>
<DecisionButtonsEditNotAllowed index={"defaultID"}></DecisionButtonsEditNotAllowed>
</div>
</li> */

export const AnnotationButton = ({
                                   index,
                                   quantitative_statement,
                                   analysis_name,
                                   paper_id,
                                   bg_color,
                                   children,
                                 }: {
  index: number;
  quantitative_statement: QuantitativeStatement;
  analysis_name: string;
  paper_id: string;
  bg_color: string;
  children: React.ReactNode;
}) => {
  const [isVisible, setIsVisible] = useState(false);

  const handleClick = () => {
    const annotations = document.querySelectorAll(".annotation_" + index);
    if (!isVisible) {
      annotations.forEach(element => {
        (element as HTMLElement).classList.add(bg_color.split(' ')[0], bg_color.split(' ')[1]);
      });
    } else {
      annotations.forEach(element => {
        (element as HTMLElement).classList.remove(bg_color.split(' ')[0], bg_color.split(' ')[1]);
      });
    }
    setIsVisible(!isVisible);
  };

  return (
    <span id={`Q${index}`}>
      <button onClick={handleClick} id={`dropdownDefaultButton`}
              data-dropdown-toggle={`dropdown${index}`} data-dropdown-trigger="click"
              className={`group contents`} type={`button`}>
        {children}
      </button>
      {isVisible &&
        <div id={`dropdown${index}`}
             className="z-10 w-3/4 my-1.5 mx-auto bg-white rounded-lg shadow dark:bg-gray-700">
          <AnnotationTable analysis_name={analysis_name} paper_id={paper_id} index={index}
                           quantitative_statement={quantitative_statement}></AnnotationTable>
        </div>
      }
    </span>
  );
};

/*
const QuantitativeStatement = ({
                                 paper_id,
                                 index,
                                 quantitative_statement,
                               }: {
  paper_id: string;
  index: number;
  quantitative_statement: RawQuantitativeStatement;
}) => (
  <>
    {index ?
      <div id={`dropdown${index}`}
           className="z-10 w-3/4 my-1.5 mx-auto bg-white rounded-lg shadow dark:bg-gray-700">
        <AnnotationTable paper_id={paper_id} quantitative_statement={quantitative_statement}></AnnotationTable>
      </div>
    :
      <div id="dropdown"
           className="z-10 w-3/4 my-1.5 mx-auto bg-white rounded-lg shadow dark:bg-gray-700">
        <AnnotationTable paper_id={paper_id} quantitative_statement={quantitative_statement}></AnnotationTable>
      </div>
    }
  </>
);
 */

export const AnnotationSpan = ({
                                 children,
                                 id = "",
                                 bg_color = "bg-yellow-200 group-hover:bg-yellow-300",
                               }: {
  children: React.ReactNode;
  id?: string;
  bg_color?: string;
}) => (
  <a className={`${id} relative px-1 py-0.5 -mx-1 rounded-full ${bg_color}`}>
    {children}
  </a>
);

export const CiteSpan = ({url = "#!", text}: { url?: string, text: string }) => (
  <a href={url}>
    <sup className={`border-b border-dotted border-current hover:border-b-2 hover:border-solid hover:font-medium`}>{text}</sup>
  </a>
);

export const RefOrTextSpan = ({style = "", text_span}: { style?: string, text_span: TextSpan }) => {
  const { reference, text } = text_span;

  if (reference) {
    const citeProps = reference.id ? { url: `#${reference.id}` } : {};
    return (
      <span className={style}>
        <CiteSpan {...citeProps} text={text} />
      </span>
    );
  }

  return <span className={style}>{text}</span>;
};

export const TextSnippet = ({analysis_name, paper_id, text_span, quantitative_statements}: {
  analysis_name: string,
  paper_id: string,
  text_span: TextSpan,
  quantitative_statements: QuantitativeStatement[]
}) => {
  let classes: string = "";
  if (text_span.index) {
    for (const num of text_span.index) {
      classes += " annotation_" + num;
    }
  }

  useEffect(() => {
    const hash = window.location.hash;
    if (!hash) return;

    const id = hash.substring(1);

    const tryScroll = () => {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
        return true;
      }
      return false;
    };

    if (tryScroll()) return;

    const observer = new MutationObserver(() => {
      if (tryScroll()) {
        observer.disconnect();
        clearTimeout(failSafeTimeout);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    const failSafeTimeout = setTimeout(() => {
      observer.disconnect();
      console.warn(`Element with id '${id}' not found in time.`);
    }, 5000);

    return () => {
      observer.disconnect();
      clearTimeout(failSafeTimeout);
    };
  }, []);

  return (
    <>
      {text_span.annotation ?
        <>
          {text_span.annotation.is_quantity ?
            <AnnotationButton index={text_span.annotation.index}
                              quantitative_statement={quantitative_statements[text_span.annotation.index]}
                              analysis_name={analysis_name}
                              paper_id={paper_id}
                              bg_color={text_span.annotation.bg_color}>
              <AnnotationSpan bg_color={text_span.annotation.bg_color}>
                <RefOrTextSpan text_span={text_span}></RefOrTextSpan>
              </AnnotationSpan>
            </AnnotationButton>
            :
            <>
              <AnnotationSpan id={classes} bg_color={""}>
                <RefOrTextSpan text_span={text_span}></RefOrTextSpan>
              </AnnotationSpan>
            </>
          }
        </>
        :
        <RefOrTextSpan style={"relative z-10"} text_span={text_span}></RefOrTextSpan>
      }
    </>
  );
}