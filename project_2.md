# Project 2 — Data Stories: Building Interactive Dashboards with Python Shiny

## 1. Project Details

This project asks you to apply what you have learnt this semester to build an interactive data visualization application in Python Shiny.

You will work in teams of up to 4. The brief is intentionally open-ended to reward creativity, exploration, and self-learning: choose your own topic, source or crawl your own dataset, and use the techniques from the course to tell a story you find compelling. Your application should demonstrate effective visual communication, meaningful interactivity, and solid technical implementation.

The project should go beyond static charts and basic dashboards. Aim for a more advanced visualization problem, such as:

- Interactive multidimensional visualization
- Time-series visualization and forecasting
- Spatial or spatio-temporal visualization
- Text or network visualization
- Animated visualizations
- Interactive analytical dashboards
- Visual analytics

Projects must be implemented primarily in Python and must be reproducible and well documented.

### Project Questions

In this project, the expected output is a dashboard, which is basically a collection of charts which is arranged and designed in a logical manner. You will need to build this dashboard with Python Shiny. More examples of what you can build with python Shiny can be found here.

This project is open-ended, you can select any publicly available dataset on the Internet. After that, think of an interesting question you can answer with this dataset and build a dashboard to guide the viewer through your story with this dataset. For example, you can find dataset to answer real-world questions like:

- What are the demographics of voters in the US presidential elections?
- How do income levels vary across different regions or demographics in …?
- What is the correlation between education levels and income in …?
- How has the prevalence of certain diseases changed over time?
- What are the key factors influencing life expectancy in different countries?
- How are carbon emissions distributed globally, and how have they changed over the years?
- What is the correlation between deforestation and wildlife population decline?
- What are the peak times for user engagement on different social media platforms?
- How do education levels correlate with job opportunities in different fields?
- What is the distribution of student performance in standardized tests?

Your dashboard should have at least 5 charts, and you should use at least 3 types of charts.

Additionally, you will need to deploy your shiny app on [shinyapps.io](https://www.shinyapps.io/). We believe that the free option offered on the website will be sufficient for this course.

## 2. Deadlines

### Proposal — Due 18/05

Submit the following:

- **Proposal write-up (under 500 words).** A short document covering your dataset, the question you are answering, why it matters, and why the data is challenging to visualize.
- **Wireframe sketch.** A draft layout of your dashboard — drawn in PowerPoint, Excel, draw.io, or by hand. Annotate each chart, filter, and component to indicate what data it shows and how it behaves (filtering, interaction, cross-filtering, etc.).
- **Presentation slides** covering:
  - Initial project plan
  - Dataset description
  - Planned visualization and analytical methods
  - Link to your GitHub repository

Each team will give an in-class presentation (5 minutes).

### Final Submission & Presentation — Due 07/06

Submit:

- Source code (in main branch of the provided Git)
- Final report (up to 6 pages), written in LaTEX
- Presentation slides

Each team will also give an in-class presentation (8 minutes) with a live demo.

## 3. Deliverables

### 3.1 Proposal

The proposal consists of three components: a write-up, a wireframe, and a short presentation. Together they should answer *what* you are building, *why* it matters, and *how* you plan to build it.

#### Write-up (under 500 words)

Cover:

- **Project description.** A short summary of the idea, goals, and the question you are answering.
- **Motivation.** Why the project is interesting, what problem it addresses, and why the dataset or topic matters.
- **Dataset description.** Data source, collection method, structure, and challenges or limitations.
- **Visualization challenge.** Why this data is non-trivial to visualize — e.g. dimensionality, scale, temporal/spatial structure, sparsity, or mixed data types.

#### Wireframe

A sketched layout of your dashboard, drawn in PowerPoint, Excel, draw.io, or by hand. It should communicate the planned structure of the app without needing to be polished. For each chart, filter, or component, annotate:

- The chart type and the data it presents
- The interactive behavior (filtering, brushing, cross-filtering, tooltips, linked views, etc.)
- How the component fits into the overall story or analytical flow

#### Presentation slides

Slides should summarize:

- Initial project plan and dashboard story
- Dataset description
- Planned visualization techniques, interactions, and analytical/ML methods
- Technologies and libraries (e.g. Python Shiny, Plotly, Pandas, Scikit-learn, GeoPandas, Altair, PyDeck)
- Development plan with task allocation per team member
- Link to your GitHub repository

#### GitHub repository

A public repo containing:

- The proposal write-up and wireframe
- Data files or data-collection scripts
- Ongoing project progress
- Documentation

### 3.2 Python Shiny Application

The application should:

- Support interactive visualization
- Let users explore and filter the data
- Surface clear analytical insights
- Tell a meaningful visual story
- Be reproducible and runnable locally

Possible features:

- Interactive filtering
- Dynamic plots
- Time-series forecasting
- Spatial analysis
- Animated visualizations
- Model comparison
- Linked visual components

### 3.3 Final Report

The report should clearly explain:

- Project motivation
- Dataset and preprocessing
- Visualization design decisions
- Interaction design
- Analytical and ML methods
- Key findings and insights
- Challenges and limitations
- Future improvements

It should also reflect on:

- Why you chose specific visualization techniques
- How interactivity strengthens the user's understanding
- How ML or predictive analytics contribute to the analysis

### 3.4 Presentation

Each team will give an in-class presentation and live demo. Cover:

- Problem statement
- Dataset overview
- Visualization techniques
- Interactive features
- ML or predictive components
- System architecture
- Key findings
- Challenges and lessons learnt

Demonstrate the application live during the presentation.

## 4. Grading

| Category | Percentage |
| --- | --- |
| Proposal | 25% |
| Presentation & Demo | 35% |
| Final Project & Write-up | 40% |

## 5. Evaluation Criteria

**Visualization & design**

- Quality of visualizations
- Clarity and aesthetics
- Effectiveness of visual communication
- Storytelling

**Technical complexity**

- Advanced visualization techniques
- Interactive functionality
- Dashboard complexity
- Data processing pipeline

**Machine learning & analytics (COMP 5120)**

Projects are encouraged to incorporate:

- Machine learning for time-series analysis
- Spatial data analysis
- Forecasting and prediction
- Spatio-temporal analytics
- Predictive models embedded in visual analytics workflows

Projects that successfully combine machine learning, prediction, interactive visualization, and analytical storytelling will receive higher consideration.

**Reproducibility & code quality**

- Clean, organized code
- Documentation quality
- Reproducibility
- GitHub organization

**Presentation**

- Clarity of communication
- Demo quality
- Technical understanding
- Ability to answer questions

## 6. Recommended Project Directions

Some ideas to spark thinking:

- Interactive climate or weather forecasting dashboard
- Spatial analysis of traffic or transportation data
- Stock market forecasting visualization
- Social network visualization
- Text analytics dashboard
- Interactive sports analytics system
- Crime or public-health spatio-temporal visualization
- Generative art and visualization systems
- Accessibility-focused visualization tools
- Real-time monitoring dashboards

You are encouraged to go beyond this list with creative, technically challenging ideas.
