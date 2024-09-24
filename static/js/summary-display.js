function displaySummary(data) {
    const summaryContainer = document.getElementById('summary-container');
    if (!summaryContainer) {
        console.error('Summary container not found');
        return;
    }

    summaryContainer.classList.remove('hidden');

    // Set video title
    const titleElement = document.getElementById('video-title');
    if (titleElement) {
        titleElement.textContent = data.summary.title;
    }

    // Embed video
    const embedContainer = document.getElementById('video-embed');
    if (embedContainer) {
        const embedHtml = `<iframe width="560" height="315" src="https://www.youtube.com/embed/${data.video_id}" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
        embedContainer.innerHTML = embedHtml;
    }

    // Display metadata
    const metadataContainer = document.getElementById('video-metadata');
    if (metadataContainer) {
        const metadataHtml = `
            <p><strong>Views:</strong> ${data.summary.video_views}</p>
            <p><strong>Likes:</strong> ${data.raw_data.like_count}</p>
            <p><strong>Comments:</strong> ${data.raw_data.comment_count}</p>
            <p><strong>Published:</strong> ${new Date(data.raw_data.date_published).toLocaleDateString()}</p>
        `;
        metadataContainer.innerHTML = metadataHtml;
    }

    // Display summary
    const summaryContent = document.getElementById('video-summary');
    if (summaryContent) {
        const summaryHtml = `
            <div>
                <h3 class="text-xl font-bold">Overview</h3>
                <p>${data.summary.overview}</p>
            </div>
            <div>
                <h3 class="text-xl font-bold">Key Points</h3>
                <ul class="list-disc pl-5">
                    ${data.summary.key_points.map(point => `
                        <li>
                            <strong>${point.point_title}</strong>: ${point.point_description}
                        </li>
                    `).join('')}
                </ul>
            </div>
            <div>
                <h3 class="text-xl font-bold">Engagement Analysis</h3>
                <p>${data.summary.engagement_analysis}</p>
            </div>
            <div>
                <h3 class="text-xl font-bold">Target Audience</h3>
                <p>${data.summary.target_audience}</p>
            </div>
            <div>
                <h3 class="text-xl font-bold">Improvement Suggestions</h3>
                <ul class="list-disc pl-5">
                    ${data.summary.improvement_suggestions.map(suggestion => `
                        <li>
                            <strong>${suggestion.improvement_title}</strong>: ${suggestion.improvement_description}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
        summaryContent.innerHTML = summaryHtml;
    }

    // Scroll to the summary container
    summaryContainer.scrollIntoView({ behavior: 'smooth' });
}