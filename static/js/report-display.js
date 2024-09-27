// report-display.js

function displayReport(report) {
    const reportContainer = document.getElementById('report-container');
    reportContainer.innerHTML = ''; // Clear previous content
    reportContainer.classList.remove('hidden');

    // Create title
    const titleContainer = document.createElement('div');
    titleContainer.className = 'text-center mb-6';
    
    const title = document.createElement('h2');
    title.textContent = report.consultation_report.title;
    title.className = 'text-2xl font-bold';
    titleContainer.appendChild(title);

    reportContainer.appendChild(titleContainer);

    // Create grid container
    const gridContainer = document.createElement('div');
    gridContainer.className = 'grid grid-cols-1 md:grid-cols-2 gap-6';
    reportContainer.appendChild(gridContainer);

    report.consultation_report.sections.forEach(section => {
        const sectionDiv = document.createElement('div');
        sectionDiv.className = 'bg-zinc-200 rounded-lg p-6 shadow-md';

        const sectionTitle = document.createElement('h3');
        sectionTitle.textContent = section.subtitle;
        sectionTitle.className = 'text-xl font-semibold mb-4 text-zinc-700';
        sectionDiv.appendChild(sectionTitle);

        if (typeof section.content === 'string') {
            const content = document.createElement('p');
            content.textContent = section.content;
            content.className = 'text-zinc-700';
            sectionDiv.appendChild(content);
        } else if (Array.isArray(section.content)) {
            section.content.forEach(subSection => {
                if (subSection.sections) {
                    subSection.sections.forEach(subSubSection => {
                        const subTitle = document.createElement('h4');
                        subTitle.textContent = subSubSection.subtitle;
                        subTitle.className = 'text-lg font-light mt-4 mb-2 text-zinc-600';
                        sectionDiv.appendChild(subTitle);

        const subContent = document.createElement('p');
                        subContent.textContent = subSubSection.content;
                        subContent.className = 'text-gray-700';
                        sectionDiv.appendChild(subContent);
                    });
                }
            });
        }

        gridContainer.appendChild(sectionDiv);
    });

    // Scroll to the report container
    reportContainer.scrollIntoView({ behavior: 'smooth' });
}