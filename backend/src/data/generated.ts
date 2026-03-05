// Re-export from the pipeline-generated file.
// When the pipeline runs 06_seed, it overwrites this file directly.
// Until then, re-export from the existing generatedData.ts.
export {
  subjects,
  chapters,
  topics,
  topicContents,
  pyqs,
  pyqExplanations,
} from '../generatedData'
